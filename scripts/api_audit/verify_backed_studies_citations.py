#!/usr/bin/env python3
"""Content-verify every PubMed citation in backed_clinical_studies.json.

This file (197 entries, ~438 distinct PMIDs) is the clinical-evidence-bonus
backbone and is NOT covered by verify_all_citations_content.py. Each
references_structured[] item stores the PMID *and the title recorded when it was
added*, which gives two independent checks per PMID:

  1. STORED-vs-LIVE title, at two sensitivities:
       TITLE-MISMATCH (<0.30 word overlap) -- the stored title barely resembles
         the live record: the PMID is probably wrong or the title fabricated.
       TITLE-DRIFT (unequal but recognisable) -- right paper, wrong string.
         Exact equality is the only sound test here; the overlap gate alone was
         blind to nine live defects on 2026-08-06, including a 125-char markup
         truncation and a "healthy adolescents" / "healthy adults" population
         error, both of which ship to users through detail_blobs.
  2. INGREDIENT content: does the live title+abstract+MeSH share a topic word
     with the entry's ingredient (standard_name / aliases / category /
     key_endpoints)? No overlap => a possible wrong-topic ("ghost") reference.

Inline "PMID NNNNN" mentions in notable_studies are also checked (no stored
title there, so only the ingredient content check applies).

Flagged items are for MANUAL review (both heuristics have false positives).

Usage:
    python3 scripts/api_audit/verify_backed_studies_citations.py
    python3 scripts/api_audit/verify_backed_studies_citations.py --strict

``--strict`` turns this report into a release gate. TITLE-MISMATCH, TITLE-DRIFT
and not-found are hard failures. GHOST-SUSPECT is a heuristic with real false
positives, so a suspect fails the gate only until it is reviewed and recorded in
``scripts/data/backed_studies_ghost_review.json`` with a rationale -- an
unreviewed suspect blocks, a reviewed one does not.
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


ACK_PATH = REPO / "scripts" / "data" / "backed_studies_ghost_review.json"


def _acknowledged_ghosts() -> dict:
    """Reviewed ghost-suspects, keyed "PMID:entry_id"."""
    if not ACK_PATH.is_file():
        return {}
    payload = json.loads(ACK_PATH.read_text(encoding="utf-8"))
    reviewed = payload.get("reviewed") or []
    out = {}
    for item in reviewed:
        if not isinstance(item, dict):
            continue
        key = f"{item.get('pmid')}:{item.get('entry_id')}"
        if item.get("rationale"):
            out[key] = item
    return out


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

    ok, ghosts, mismatches, drifts, notfound = 0, [], [], [], []
    for p in pmids:
        c = claims[p]
        a = arts.get(p)
        if not a:
            notfound.append((p, c["eid"]))
            continue
        live_title = (a.get("title") or "").strip()
        text = words(live_title) | words(a.get("abstract"))
        text |= {m.lower() for m in (a.get("mesh_terms") or [])}
        text |= words(*(a.get("mesh_terms") or []))

        # check 1: stored-vs-live title
        stored_bad = None
        if c["stored"]:
            best = max(title_overlap(s, live_title) for s in c["stored"])
            if best < 0.30:  # stored title barely resembles the live title
                stored_bad = (sorted(c["stored"])[0][:70], live_title[:70], round(best, 2))

        # check 1b: EXACT stored-vs-live title.
        # The 0.30 overlap gate above only catches a title that barely
        # resembles the live record. It is blind to the two defects that
        # actually occur: (a) truncation at inline markup -- findtext()
        # stops at the first <i>/<sup>, so "...elevates NAD" scores ~0.8
        # and passes; and (b) a single wrong word -- "healthy adolescents"
        # vs "healthy adults" scores ~0.9 and passes. Both ship to users
        # via detail_blobs. 2026-08-06: nine such defects were live while
        # this script reported TITLE-MISMATCH=0. Exact equality is the
        # only sound test; anything unequal but recognisable is DRIFT.
        stored_drift = []
        if not stored_bad:
            stored_drift = sorted(s for s in c["stored"] if s.strip() != live_title)

        # check 2: ingredient content overlap
        ingredient_overlap = bool(c["tw"] & text)

        if stored_bad:
            mismatches.append((p, c["eid"], *stored_bad))
        elif stored_drift:
            drifts.append((p, c["eid"], stored_drift[0], live_title))
        elif not ingredient_overlap and c["tw"]:
            ghosts.append((p, c["eid"], live_title[:75], sorted(c["tw"])[:6]))
        else:
            ok += 1

    print(f"RESULT: ok={ok}  TITLE-MISMATCH={len(mismatches)}  "
          f"TITLE-DRIFT={len(drifts)}  "
          f"GHOST-SUSPECT={len(ghosts)}  not-found={len(notfound)}\n")
    if notfound:
        print("=== NOT FOUND (PMID did not resolve) ===")
        print("  WARNING: fetch_articles() swallows per-batch network errors, so a")
        print("  timeout or DNS failure is indistinguishable here from a PMID that")
        print("  genuinely does not exist. Re-run before treating any of these as a")
        print("  hallucinated identifier.")
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
    if drifts:
        print("=== TITLE DRIFT (right paper, stored title != live byte-for-byte) ===")
        print("  Usually markup truncation (<i> species name, <sup>®/+</sup>) or a")
        print("  single wrong word. The PMID is correct; the stored string is not,")
        print("  and it ships to users in detail_blobs. Repair from the live title.")
        for p, eid, stored, live in drifts:
            print(f"\n  PMID {p}  ({eid})   missing {len(live) - len(stored)} chars")
            print(f"    stored: {stored!r}")
            print(f"    live  : {live!r}")
        print()
    if ghosts:
        print("=== GHOST-SUSPECT (live title shares no ingredient word — MANUAL REVIEW) ===")
        for p, eid, title, tw in ghosts:
            print(f"  PMID {p}  ({eid})")
            print(f"    live title : {title}")
            print(f"    ingredient : {tw}")
        print()
    if not (mismatches or drifts or ghosts or notfound):
        print("Every cited PMID resolves, matches its stored title EXACTLY, and "
              "shares an ingredient word.")

    if "--strict" not in sys.argv:
        return 0

    acknowledged = _acknowledged_ghosts()
    unreviewed = [
        (p, eid) for p, eid, _title, _tw in ghosts
        if f"{p}:{eid}" not in acknowledged
    ]
    hard = len(mismatches) + len(drifts) + len(notfound)
    if hard or unreviewed:
        print("STRICT: backed_clinical_studies citation gate FAILED")
        if hard:
            print(f"  hard findings: mismatch={len(mismatches)} "
                  f"drift={len(drifts)} not-found={len(notfound)}")
        for p, eid in unreviewed:
            print(f"  unreviewed ghost-suspect: PMID {p} ({eid}) — review it and "
                  f"record the rationale in {ACK_PATH.relative_to(REPO)}")
        return 1
    if ghosts:
        print(f"STRICT: {len(ghosts)} ghost-suspect(s), all reviewed and "
              f"recorded in {ACK_PATH.relative_to(REPO)}")
    print("STRICT: backed_clinical_studies citation gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
