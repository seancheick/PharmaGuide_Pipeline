#!/usr/bin/env python3
"""Content-verify every PubMed citation in backed_clinical_studies.json.

This file (197 entries, ~438 distinct PMIDs) is the clinical-evidence-bonus
backbone and is NOT covered by verify_all_citations_content.py. Each
references_structured[] item stores the PMID *and the title recorded when it was
added*, which gives two independent checks per PMID:

  1. STORED-vs-LIVE title: fetch the live PubMed title and compare to the stored
     title. A mismatch means the PMID number is wrong / was corrupted / the
     stored title was fabricated.
  2. INGREDIENT content: does the live title+abstract+MeSH share a topic word
     with the entry's ingredient (standard_name / aliases / category /
     key_endpoints)? No overlap => a possible wrong-topic ("ghost") reference.

Inline "PMID NNNNN" mentions in notable_studies are also checked (no stored
title there, so only the ingredient content check applies).

Flagged items are for MANUAL review (both heuristics have false positives).

Usage:  python3 scripts/api_audit/verify_backed_studies_citations.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from verify_all_citations_content import fetch_articles  # noqa: E402

DATA = REPO / "scripts" / "data" / "backed_clinical_studies.json"
PMID_INLINE = re.compile(r"PMID[:\s]+(\d+)")

STOP = {
    "the", "and", "for", "with", "study", "trial", "randomized", "controlled",
    "double", "blind", "placebo", "effect", "effects", "efficacy", "safety",
    "human", "patients", "adults", "clinical", "supplementation", "supplement",
    "administration", "extract", "acid", "complex", "during", "versus", "from",
    "response", "levels", "health", "using", "based", "review", "meta", "analysis",
    "systematic", "chronic", "acute", "oral", "daily", "high", "low", "dose",
}


def words(*texts: str) -> set[str]:
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        for w in re.findall(r"[a-z]{4,}", str(t).lower()):
            if w not in STOP:
                out.add(w)
    return out


def title_overlap(a: str, b: str) -> float:
    """Jaccard-ish overlap of the two title word sets (0..1)."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def main() -> int:
    d = json.loads(DATA.read_text())
    entries = d["backed_clinical_studies"]

    # pmid -> {entry_id, topic_words, stored_titles(set)}
    claims: dict[str, dict] = {}
    for e in entries:
        eid = e.get("id", "?")
        tw = words(
            e.get("standard_name"),
            " ".join(e.get("aliases") or []),
            e.get("category"),
            " ".join(str(k) for k in (e.get("key_endpoints") or [])),
            " ".join(e.get("health_goals_supported") or []),
        )
        for rs in (e.get("references_structured") or []):
            p = str(rs.get("pmid") or "").strip()
            if p.isdigit():
                c = claims.setdefault(p, {"eid": eid, "tw": set(), "stored": set()})
                c["tw"] |= tw
                if rs.get("title"):
                    c["stored"].add(rs["title"])
        for p in PMID_INLINE.findall(json.dumps(e)):
            c = claims.setdefault(p, {"eid": eid, "tw": set(), "stored": set()})
            c["tw"] |= tw

    pmids = sorted(claims)
    print(f"Entries: {len(entries)} | distinct PMIDs: {len(pmids)}\n")
    print(f"Fetching {len(pmids)} PMIDs live from PubMed efetch...\n")
    arts = fetch_articles(pmids)

    ok, ghosts, mismatches, notfound = 0, [], [], []
    for p in pmids:
        c = claims[p]
        a = arts.get(p)
        if not a:
            notfound.append((p, c["eid"]))
            continue
        live_title = a.get("title", "")
        text = words(live_title) | words(a.get("abstract"))
        text |= {m.lower() for m in (a.get("mesh_terms") or [])}
        text |= words(*(a.get("mesh_terms") or []))

        # check 1: stored-vs-live title
        stored_bad = None
        if c["stored"]:
            best = max(title_overlap(s, live_title) for s in c["stored"])
            if best < 0.30:  # stored title barely resembles the live title
                stored_bad = (sorted(c["stored"])[0][:70], live_title[:70], round(best, 2))

        # check 2: ingredient content overlap
        ingredient_overlap = bool(c["tw"] & text)

        if stored_bad:
            mismatches.append((p, c["eid"], *stored_bad))
        elif not ingredient_overlap and c["tw"]:
            ghosts.append((p, c["eid"], live_title[:75], sorted(c["tw"])[:6]))
        else:
            ok += 1

    print(f"RESULT: ok={ok}  TITLE-MISMATCH={len(mismatches)}  "
          f"GHOST-SUSPECT={len(ghosts)}  not-found={len(notfound)}\n")
    if notfound:
        print("=== NOT FOUND (PMID did not resolve) ===")
        for p, eid in notfound:
            print(f"  {p}  ({eid})")
        print()
    if mismatches:
        print("=== TITLE MISMATCH (stored title != live PubMed title — likely wrong PMID) ===")
        for p, eid, stored, live, ov in mismatches:
            print(f"  PMID {p}  ({eid})  overlap={ov}")
            print(f"    stored: {stored}")
            print(f"    live  : {live}")
        print()
    if ghosts:
        print("=== GHOST-SUSPECT (live title shares no ingredient word — MANUAL REVIEW) ===")
        for p, eid, title, tw in ghosts:
            print(f"  PMID {p}  ({eid})")
            print(f"    live title : {title}")
            print(f"    ingredient : {tw}")
        print()
    if not (mismatches or ghosts or notfound):
        print("Every cited PMID resolves, matches its stored title, and shares an ingredient word.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
