#!/usr/bin/env python3
"""Deterministic QA over the Wave 2 screening output (read-only).

A screener's output is untrusted input. This checks the things a model cannot
be relied on to get right about itself, before any of it reaches central
verification:

  * every PMID it names - selected, handoff or excluded - exists in that
    identity's own retrieval, so nothing was recalled from memory;
  * no free-text field smuggles a verbatim span from the abstract: the brief
    said paraphrase, and a long exact match means a quote was written anyway
    (quotes from a screener are re-extracted centrally regardless, so any that
    appear here are rejected rather than repaired);
  * class and content agree - no_qualifying and handoff_only carry no selected
    record, curate carries at least one;
  * the shortlist it read is the shortlist it was given.

Nothing is repaired. The output is the ledger that keeps the drafts honestly
labelled as triage.

    python3 scripts/audits/evidence_expansion_2026_09/qa_wave2_screens.py \
        --screen-dir <dir> --packet-dir <dir> --candidates-dir <dir>
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
FREE_TEXT = ("one_line_reason", "population", "intervention", "dose_as_stated",
             "primary_outcome", "why_selected", "note", "reason")
# Shortest span treated as copied rather than coincidental phrasing.
VERBATIM_WINDOW = 60


def free_text_values(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FREE_TEXT and isinstance(value, str):
                yield key, value
            else:
                yield from free_text_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from free_text_values(item)


def longest_verbatim(text: str, corpus: str) -> str | None:
    """Longest span of `text` (>= VERBATIM_WINDOW chars) that appears in `corpus`."""
    if not text or not corpus or len(text) < VERBATIM_WINDOW:
        return None
    for size in range(len(text), VERBATIM_WINDOW - 1, -1):
        for start in range(0, len(text) - size + 1):
            span = text[start:start + size]
            if span in corpus:
                return span
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-dir", required=True, type=Path)
    parser.add_argument("--packet-dir", required=True, type=Path)
    parser.add_argument("--candidates-dir", required=True, type=Path)
    parser.add_argument("--out", default="wave2_screen_qa.json")
    args = parser.parse_args()

    rows, totals = [], collections.Counter()
    for path in sorted(args.screen_dir.glob("*.screen.json")):
        screen = json.loads(path.read_text())
        cid = screen["canonical_id"]
        retrieval = json.loads((args.candidates_dir / f"{cid}.json").read_text())
        known = {r["pmid"] for r in retrieval["records"]}
        abstracts = " \n ".join(r.get("abstract") or "" for r in retrieval["records"])
        packet = json.loads((args.packet_dir / f"{cid}.json").read_text())
        given = {s["pmid"] for s in packet["shortlist"]}

        named = ([str(s.get("pmid")) for s in screen.get("selected") or []]
                 + [str(s.get("pmid")) for s in screen.get("handoff_pmids") or []]
                 + [str(s.get("pmid")) for s in screen.get("excluded_pmids") or []])
        unknown = sorted({p for p in named if p not in known})
        outside_shortlist = sorted({str(s.get("pmid")) for s in screen.get("selected") or []} - given)

        verbatim = []
        for field, value in free_text_values(screen):
            span = longest_verbatim(value, abstracts)
            if span:
                verbatim.append({"field": field, "chars": len(span), "span": span[:120]})

        cls = screen.get("recommended_class")
        selected = len(screen.get("selected") or [])
        class_conflict = ((cls in ("no_qualifying", "handoff_only") and selected)
                          or (cls == "curate" and not selected))
        row = {"canonical_id": cid, "recommended_class": cls, "selected": selected,
               "handoffs": len(screen.get("handoff_pmids") or []),
               "excluded": len(screen.get("excluded_pmids") or []),
               "shortlist_given": len(given),
               "pmids_not_in_retrieval": unknown,
               "selected_outside_shortlist": outside_shortlist,
               "verbatim_spans": verbatim,
               "class_conflict": bool(class_conflict)}
        rows.append(row)
        totals["identities"] += 1
        totals["pmids_not_in_retrieval"] += len(unknown)
        totals["selected_outside_shortlist"] += len(outside_shortlist)
        totals["verbatim_spans"] += len(verbatim)
        totals["class_conflicts"] += bool(class_conflict)
        totals[f"class_{cls}"] += 1

    payload = {"_metadata": dict(totals) | {
        "verbatim_window_chars": VERBATIM_WINDOW,
        "purpose": "QA ledger for Wave 2 screening drafts; nothing repaired.",
        "verdict": "Screens are triage. Every fact that reaches a pending context is re-extracted "
                   "centrally from the live source, so a span reported here is rejected, not fixed."},
        "identities": rows}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    for row in rows:
        if row["pmids_not_in_retrieval"] or row["selected_outside_shortlist"] or row["class_conflict"]:
            print(f"  !! {row['canonical_id']}: unknown={row['pmids_not_in_retrieval']} "
                  f"outside={row['selected_outside_shortlist']} class_conflict={row['class_conflict']}")
        if row["verbatim_spans"]:
            print(f"  ~  {row['canonical_id']}: {len(row['verbatim_spans'])} verbatim span(s), "
                  f"longest {max(v['chars'] for v in row['verbatim_spans'])} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
