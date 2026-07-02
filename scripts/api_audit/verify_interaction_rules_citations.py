#!/usr/bin/env python3
"""Content-verify every PubMed citation in ingredient_interaction_rules.json.

The mandated content verifier (verify_all_citations_content.py) does NOT cover
this file: its PMIDs live nested under interaction_rules[].condition_rules[] /
drug_class_rules[] / pregnancy_lactation.sources[], not a flat array. That gap
left ~200 clinical PMIDs unchecked against the live PubMed API.

This walks the nested structure, fetches each cited PMID live (reusing the same
efetch path as verify_all_citations_content.fetch_articles), and flags any PMID
whose real title+abstract+MeSH share NO ingredient/mechanism/condition word with
the claim it is cited for — the signature of a wrong-topic "ghost" reference.

Flagged PMIDs are for MANUAL review (the overlap heuristic has false positives
when an ingredient is named differently in the abstract) — never auto-edited.

Usage:  python3 scripts/api_audit/verify_interaction_rules_citations.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# load .env (PUBMED_API_KEY) the same way the audit tools do
_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from verify_all_citations_content import fetch_articles  # noqa: E402

RULES = REPO / "scripts" / "data" / "ingredient_interaction_rules.json"
PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")

STOP = {
    "the", "and", "for", "with", "may", "can", "of", "in", "to", "a", "an", "at",
    "on", "is", "are", "use", "dose", "doses", "risk", "effect", "effects", "high",
    "low", "level", "levels", "increase", "increased", "increases", "decrease",
    "lower", "lowers", "raise", "raises", "supplement", "supplements", "supplemental",
    "intake", "daily", "study", "studies", "trial", "trials", "clinical", "human",
    "patients", "adults", "from", "this", "that", "these", "those", "have", "has",
    "been", "when", "who", "via", "per", "day", "above", "below", "than", "more",
    "less", "also", "some", "most", "using", "used", "acid",  # 'acid' too generic
}

# canonical_id prefixes to strip so the ingredient name survives as topic words
PREFIX_RE = re.compile(r"^(BANNED|RECALLED|IQM|HARMFUL|INT|RULE|BOTANICAL|PROBIOTIC)_", re.I)


def words(*texts: str) -> set[str]:
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        for w in re.findall(r"[a-z]{4,}", str(t).lower()):
            if w not in STOP:
                out.add(w)
    return out


def canonical_words(canonical_id: str) -> set[str]:
    if not canonical_id:
        return set()
    stripped = PREFIX_RE.sub("", canonical_id)
    return words(stripped.replace("_", " "))


def main() -> int:
    d = __import__("json").loads(RULES.read_text())
    rules = d.get("interaction_rules") or []

    # pmid -> list of (rule_id, subrule_label, topic_words)
    claims: dict[str, list[tuple]] = {}
    total_sources = 0
    for r in rules:
        rid = r.get("id", "?")
        canon = (r.get("subject_ref") or {}).get("canonical_id") or ""
        cwords = canonical_words(canon)

        buckets = []
        for cr in (r.get("condition_rules") or []):
            buckets.append((f"condition:{cr.get('condition_id')}", cr))
        for dr in (r.get("drug_class_rules") or []):
            buckets.append((f"drug:{dr.get('drug_class_id')}", dr))
        pl = r.get("pregnancy_lactation")
        if isinstance(pl, dict):
            buckets.append(("pregnancy_lactation", pl))

        for label, sr in buckets:
            tw = cwords | words(
                sr.get("mechanism"), sr.get("alert_headline"),
                sr.get("informational_note"), sr.get("condition_id"),
                sr.get("drug_class_id"), sr.get("notes"),
            )
            for s in (sr.get("sources") or []):
                total_sources += 1
                m = PMID_RE.search(str(s))
                if m:
                    claims.setdefault(m.group(1), []).append((rid, label, tw))

    pmids = sorted(claims)
    print(f"Rules: {len(rules)} | total source URLs: {total_sources} | "
          f"distinct PubMed PMIDs: {len(pmids)}\n")
    if not pmids:
        print("No PubMed PMIDs cited in this file.")
        return 0

    print(f"Fetching {len(pmids)} PMIDs live from PubMed efetch...\n")
    arts = fetch_articles(pmids)

    ok, ghosts, notfound = 0, [], []
    for p in pmids:
        a = arts.get(p)
        # union all topic-word sets that cite this PMID (any claim match = ok)
        tw_all: set[str] = set()
        for (_rid, _label, tw) in claims[p]:
            tw_all |= tw
        if not a:
            notfound.append(p)
            continue
        text = words(a.get("title")) | words(a.get("abstract"))
        text |= {m.lower() for m in (a.get("mesh_terms") or [])}
        text |= words(*(a.get("mesh_terms") or []))
        overlap = tw_all & text
        if overlap:
            ok += 1
        else:
            cites = "; ".join(f"{rid}/{label}" for (rid, label, _tw) in claims[p])
            ghosts.append((p, a.get("title", "")[:90], sorted(tw_all)[:8], cites))

    print(f"RESULT: on-topic={ok}  GHOST-SUSPECT={len(ghosts)}  not-found={len(notfound)}\n")
    if notfound:
        print("=== NOT FOUND (PMID did not resolve — verify manually) ===")
        for p in notfound:
            cites = "; ".join(f"{rid}/{label}" for (rid, label, _tw) in claims[p])
            print(f"  {p}   cited by: {cites}")
        print()
    if ghosts:
        print("=== GHOST-SUSPECT (no topic-word overlap — MANUAL REVIEW each) ===")
        for p, title, tw, cites in ghosts:
            print(f"  PMID {p}")
            print(f"    real title : {title}")
            print(f"    claim words: {tw}")
            print(f"    cited by   : {cites}")
        print()
    else:
        print("No ghost-suspects: every cited PMID shares a topic word with its claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
