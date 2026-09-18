#!/usr/bin/env python3
"""Deterministic pre-screen over a wave's retrieved candidate records (read-only).

Discovery returns everything the three bounded queries found. Most of it can be
classified without judgement: a case report is not efficacy evidence, a record
indexed Animals-without-Humans is not human evidence, a topical or intravenous
study is not a supplement exposure. Doing that here, in code, means a reader only
looks at records that could actually qualify — and means the rejection reason is
reproducible instead of remembered.

Nothing is discarded: every record keeps a bucket and a reason, and the full
retrieval stays on disk. This assigns no direction, extracts no dose, and reads
no result. It ranks what a screener must read.

    python3 scripts/audits/evidence_expansion_2026_09/prescreen_candidates.py \
        --candidates-dir <dir> --out <prescreen.json> [--shortlist 12]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent

SR_TYPES = {"Meta-Analysis", "Systematic Review"}
RCT_TYPES = {"Randomized Controlled Trial"}
TRIAL_TYPES = {"Clinical Trial", "Controlled Clinical Trial", "Clinical Trial, Phase I",
               "Clinical Trial, Phase II", "Clinical Trial, Phase III", "Clinical Trial, Phase IV",
               "Pragmatic Clinical Trial", "Equivalence Trial"}
GUIDELINE_TYPES = {"Practice Guideline", "Guideline", "Consensus Development Conference"}
OBSERVATIONAL_TYPES = {"Observational Study", "Comparative Study", "Multicenter Study",
                       "Evaluation Study", "Twin Study", "Validation Study"}
NOISE_TYPES = {"Case Reports", "Letter", "Editorial", "Comment", "News", "Published Erratum",
               "Retraction of Publication", "Retracted Publication", "Biography", "Historical Article",
               "Portrait", "Address", "Congress", "Bibliography"}

# A safety / PK / interaction record belongs to another owner. Matched on the
# TITLE only: an abstract mentioning adverse events is still an efficacy trial.
SAFETY_TITLE = re.compile(
    r"\b(poisoning|toxicit|overdose|intoxicat|adverse (event|effect|reaction)|hepatotoxic|nephrotoxic|"
    r"safety profile|drug interaction|herb-drug|pharmacokinetic|bioavailab|absorption kinetics|"
    r"case report|fatal|death|carcinogen|teratogen|mutagen)", re.I)
# Exposures a supplement label cannot deliver.
NON_ORAL_TITLE = re.compile(
    r"\b(topical|intravenous|\biv\b|infusion|injection|inhal|nebuli|gel\b|cream\b|ointment|lotion|"
    r"irrigation|enema|rectal|vaginal|ocular|eye drop|mouthwash|dentifrice|toothpaste|shampoo|"
    r"transdermal|subcutaneous|intraperitoneal|intramuscular|catheter|dialysis|hemoperfusion)", re.I)
IN_VITRO_TITLE = re.compile(r"\b(in vitro|in silico|cell line|molecular docking|cytotox)", re.I)
# PubMed indexes publication types late, and never for some journals. A record
# typed only "Journal Article" can still be a human trial, so recall comes from
# the abstract: an interventional design word AND a human-participant word.
TRIAL_DESIGN_ABSTRACT = re.compile(
    r"\b(randomi[sz]ed|randomi[sz]ation|placebo-controlled|double-blind|single-blind|"
    r"cross-?over (design|trial|study)|allocated to receive|assigned to receive)", re.I)
HUMAN_PARTICIPANT_ABSTRACT = re.compile(
    r"\b(patients|participants|subjects|volunteers|men\b|women\b|adults|children|infants|"
    r"individuals)\b", re.I)
NONHUMAN_ABSTRACT = re.compile(r"\b(mice|mouse|rats?\b|rabbits?|piglets?|broilers?|in vitro|cell line)", re.I)


def design_of(types: set[str]) -> str:
    if types & SR_TYPES:
        return "systematic_review_meta"
    if types & GUIDELINE_TYPES:
        return "guideline"
    if types & RCT_TYPES:
        return "rct"
    if types & TRIAL_TYPES:
        return "clinical_trial"
    if types & NOISE_TYPES:
        return "case_report_or_note"
    if "Review" in types:
        return "narrative_review"
    if types & OBSERVATIONAL_TYPES:
        return "observational"
    return "unclassified"


def human_signal(mesh: list[str]) -> str:
    terms = set(mesh or [])
    if "Humans" in terms:
        return "human_indexed"
    if "Animals" in terms:
        return "nonhuman_indexed"
    if not terms:
        return "not_indexed_yet"
    return "human_status_unstated"


def classify(record: dict) -> dict:
    types = set(record.get("publication_types") or [])
    title = record.get("title") or ""
    design = design_of(types)
    human = human_signal(record.get("mesh_terms") or [])
    integrity = ("retracted" if record.get("retracted")
                 else "expression_of_concern" if record.get("expression_of_concern")
                 else "erratum" if record.get("has_erratum") else "none")

    if integrity in ("retracted", "expression_of_concern"):
        return {"bucket": "integrity_hold", "reason": integrity, "design": design, "human": human}
    if human == "nonhuman_indexed":
        return {"bucket": "not_human", "reason": "indexed Animals without Humans", "design": design, "human": human}
    if IN_VITRO_TITLE.search(title):
        return {"bucket": "not_human", "reason": "in vitro / in silico in title", "design": design, "human": human}
    if design == "case_report_or_note":
        return {"bucket": "safety_or_note", "reason": "case report, letter, editorial or comment",
                "design": design, "human": human}
    if SAFETY_TITLE.search(title):
        return {"bucket": "safety_pk_handoff", "reason": "safety, PK or interaction subject in title",
                "design": design, "human": human}
    if NON_ORAL_TITLE.search(title):
        return {"bucket": "wrong_exposure", "reason": "non-oral route in title", "design": design, "human": human}
    if design in ("systematic_review_meta", "guideline", "rct", "clinical_trial"):
        return {"bucket": "efficacy_candidate", "reason": f"human {design}", "design": design, "human": human}
    if design in ("observational", "narrative_review"):
        return {"bucket": "lower_tier", "reason": design, "design": design, "human": human}
    abstract = record.get("abstract") or ""
    if (TRIAL_DESIGN_ABSTRACT.search(abstract) and HUMAN_PARTICIPANT_ABSTRACT.search(abstract)
            and not NONHUMAN_ABSTRACT.search(abstract)):
        return {"bucket": "efficacy_candidate", "reason": "interventional design and human participants "
                                                         "in the abstract; publication type not indexed",
                "design": "trial_unindexed", "human": human}
    return {"bucket": "unclassified", "reason": "no usable publication type", "design": design, "human": human}


RANK = {"systematic_review_meta": 0, "guideline": 1, "rct": 2, "clinical_trial": 3,
        "trial_unindexed": 4}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-dir", required=True, type=Path)
    parser.add_argument("--out", default="wave2_prescreen.json")
    parser.add_argument("--shortlist", type=int, default=12)
    args = parser.parse_args()

    identities, totals = [], collections.Counter()
    for path in sorted(glob.glob(str(args.candidates_dir / "*.json"))):
        payload = json.loads(Path(path).read_text())
        identity, records = payload["identity"], payload["records"]
        buckets = collections.Counter()
        classified = []
        for record in records:
            verdict = classify(record)
            buckets[verdict["bucket"]] += 1
            totals[verdict["bucket"]] += 1
            classified.append({**verdict, "pmid": record["pmid"], "title": record["title"],
                               "year": (record.get("published_date") or "")[:4],
                               "pmc_id": record.get("pmc_id"),
                               "query_roles": record.get("query_roles")})
        candidates = [c for c in classified if c["bucket"] == "efficacy_candidate"]
        candidates.sort(key=lambda c: (RANK.get(c["design"], 9), -int(c["year"] or 0)))
        identities.append({
            "canonical_id": identity["canonical_id"],
            "label_name": identity["label_name"],
            "catalog": identity.get("catalog"),
            "records_retrieved": len(records),
            "buckets": dict(buckets),
            "efficacy_candidates": len(candidates),
            "shortlist": candidates[:args.shortlist],
            "safety_pk_handoff_pmids": [c["pmid"] for c in classified
                                        if c["bucket"] == "safety_pk_handoff"][:20],
            "integrity_hold": [{"pmid": c["pmid"], "reason": c["reason"], "title": c["title"]}
                               for c in classified if c["bucket"] == "integrity_hold"],
        })

    identities.sort(key=lambda i: (-(i["catalog"] or {}).get("evidence_zero_products", 0)))
    payload = {"_metadata": {
        "identities": len(identities),
        "records_classified": sum(i["records_retrieved"] for i in identities),
        "buckets": dict(totals),
        "identities_with_no_efficacy_candidate": [i["canonical_id"] for i in identities
                                                  if i["efficacy_candidates"] == 0],
        "shortlist_cap_per_identity": args.shortlist,
        "note": "Deterministic classification only. No direction, dose, population or result was read."},
        "identities": identities}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
