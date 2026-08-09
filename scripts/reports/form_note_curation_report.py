#!/usr/bin/env python3
"""
form_note_curation_report.py — review aid for authoring `consumer_note`.

REVIEW AID ONLY. The build never reads this output. Nothing here is approved
copy: candidates are a starting point for a reviewer, who writes the final
`consumer_note` + `consumer_note_review` into ingredient_quality_map.json.

Why a candidate is not shippable on its own: for ~21% of forms the sentences
preceding the first audit marker are marketing prose, or claims the trailer
later corrected. `coenzymated_complex` leads with "enhanced bioavailability …
pre-converted forms ready for immediate use" while its own trailer records the
Batch 12 dephosphorylation finding that disproves it. A blacklist can prove
text unsafe; it can never prove it correct.

Ranks forms by product reach so the first tranche buys the most coverage: the
top 100 forms cover ~71% of tap-able scored ingredient rows.

Usage:
  python3 scripts/reports/form_note_curation_report.py
  python3 scripts/reports/form_note_curation_report.py --tranche 150
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
BLOBS_DIR = REPO_ROOT / "scripts" / "dist" / "detail_blobs"
OUT_DIR = Path(__file__).resolve().parent

# Where curation-workspace prose begins. Everything from the first hit onward
# is audit trail, not consumer copy.
AUDIT_MARKER_RE = re.compile(
    r"(Evidence update|Cited evidence:|API evidence trail:|CLASS-FINDING"
    r"|Misattribution|Clinician recalibration|Dr Pham|sign-off|B\d+ audit"
    r"|Batch \d+|bio_score|PMID|scripts/|UNII|UMLS|GSRS|Live API"
    r"|verification found|Kept as |reassigned|audit \d{4})",
    re.IGNORECASE,
)
# Trailer language meaning "the head claim was later revised" — the head
# sentences are suspect by construction and need the closest reading.
CORRECTION_RE = re.compile(
    r"(NOT justified|not justified|flagged|misleading|corrected|recalibrat"
    r"|marketing finding|inflation|inflated|category-error|evidence-thin"
    r"|class-poor|overstat)",
    re.IGNORECASE,
)
MARKETING_RE = re.compile(
    r"(enhanced bioavailability|ready for immediate use|pre-converted"
    r"|superior absorption|maximum absorption|highly bioavailable|premium"
    r"|optimal absorption|better absorbed|superior form|cutting-edge)",
    re.IGNORECASE,
)
SAFETY_RE = re.compile(
    r"\b(avoid|do not|don't|stop using|never|toxic|contraindicat\w*"
    r"|not recommended|harmful|risk of|warning)\b",
    re.IGNORECASE,
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def split_candidate(notes: str) -> Tuple[str, str]:
    """``(head, trailer)`` at the first audit marker."""
    head: List[str] = []
    trailer: List[str] = []
    hit = False
    for sentence in SENTENCE_RE.split(notes or ""):
        if not hit and AUDIT_MARKER_RE.search(sentence):
            hit = True
        (trailer if hit else head).append(sentence)
    return " ".join(head).strip(), " ".join(trailer).strip()


def form_tier(bio_score: Optional[float]) -> str:
    """The tier the app will render beside this note."""
    if bio_score is None:
        return "unknown"
    if bio_score >= 12:
        return "Excellent form"
    if bio_score >= 8:
        return "Good form"
    if bio_score >= 4:
        return "Fair form"
    return "Poor form"


def product_reach(blobs_dir: Path) -> Counter:
    """Products per form that is eligible to render a form note.

    A canonical ID is a nutrient identity, not a form identity: one product can
    contain several rows that resolve to different forms. Match the final
    display row to its legacy scoring row through ``raw_source_path``, the same
    linkage used by the payload builder. Rows without an assessed display form
    cannot render a note and do not belong in the curation priority queue.
    """
    reach: Counter = Counter()
    for path in sorted(blobs_dir.glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        legacy_by_source_path: Dict[str, Dict[str, Any]] = {}
        for row in blob.get("ingredients") or []:
            if not isinstance(row, dict):
                continue
            source_path = str(row.get("raw_source_path") or "").strip()
            if source_path:
                legacy_by_source_path[source_path] = row
        seen = set()
        for row in blob.get("display_ingredients") or []:
            if not isinstance(row, dict):
                continue
            analysis = row.get("analysis") or {}
            if (
                not row.get("score_included")
                or analysis.get("bio_score") is None
                or analysis.get("form_display_state") != "assessed"
            ):
                continue
            source_path = str(row.get("raw_source_path") or "").strip()
            source = legacy_by_source_path.get(source_path)
            if not source:
                continue
            form_key = str(source.get("matched_form") or "").strip()
            if form_key:
                seen.add((str(source.get("canonical_id")).strip(), form_key))
        reach.update(seen)
    return reach


def build_rows(tranche: int) -> List[Dict[str, Any]]:
    iqm = json.loads(IQM_PATH.read_text(encoding="utf-8"))
    reach = product_reach(BLOBS_DIR)

    rows: List[Dict[str, Any]] = []
    for (parent_key, form_key), products in reach.most_common():
        parent = iqm.get(parent_key)
        if not isinstance(parent, dict):
            continue
        form = (parent.get("forms") or {}).get(form_key)
        if not isinstance(form, dict):
            continue
        head, trailer = split_candidate(form.get("notes") or "")
        bio_score = form.get("bio_score")
        rows.append(
            {
                "parent": parent_key,
                "form": form_key,
                "products": products,
                "bio_score": bio_score,
                "renders_as": form_tier(bio_score),
                "already_curated": bool(form.get("consumer_note")),
                "candidate": head,
                "candidate_chars": len(head),
                "trailer_records_correction": bool(
                    trailer and CORRECTION_RE.search(trailer)
                ),
                "candidate_has_marketing": bool(head and MARKETING_RE.search(head)),
                "candidate_has_safety": bool(head and SAFETY_RE.search(head)),
                "candidate_too_short": len(head) < 60,
            }
        )

    for rank, row in enumerate(rows, 1):
        row["reach_rank"] = rank
        row["tranche_1"] = rank <= tranche
    # Riskiest first within the tranche: a corrected or marketing-flavoured
    # head is what users are being misled by today.
    rows.sort(
        key=lambda r: (
            not r["tranche_1"],
            not (
                r["trailer_records_correction"]
                or r["candidate_has_marketing"]
                or r["candidate_has_safety"]
                or r["candidate_too_short"]
            ),
            r["reach_rank"],
        )
    )
    return rows


def write_markdown(rows: List[Dict[str, Any]], tranche: int, path: Path) -> None:
    in_tranche = [r for r in rows if r["tranche_1"]]
    flagged = [
        r
        for r in in_tranche
        if r["trailer_records_correction"]
        or r["candidate_has_marketing"]
        or r["candidate_has_safety"]
        or r["candidate_too_short"]
    ]
    total_products = sum(r["products"] for r in rows) or 1
    covered = sum(r["products"] for r in in_tranche)

    lines = [
        "# Consumer form note — curation queue",
        "",
        "**Review aid. The build never reads this file.** Candidates are a",
        "starting point, not approved copy. Write the final text into",
        "`ingredient_quality_map.json` as `consumer_note` plus",
        "`consumer_note_review: {by, date}`; anything without complete review",
        "provenance fails the build (Gate A).",
        "",
        f"- Forms appearing in the catalog: **{len(rows)}**",
        f"- Tranche 1 (top {tranche} by product reach): "
        f"**{covered / total_products:.1%}** of tap-able scored appearances",
        f"- Flagged inside tranche 1 (review these first): **{len(flagged)}**",
        "",
        "Flags: `correction` — the audit trailer revises the head claim, so the",
        "candidate is stale. `marketing` / `safety` — must be rewritten or",
        "dropped; safety belongs in the warnings lane. `short` — nothing usable",
        "survives the split, write from scratch.",
        "",
        "| # | form | products | renders as | flags | candidate |",
        "|---|---|---|---|---|---|",
    ]
    for row in in_tranche:
        flags = ", ".join(
            f
            for f, on in (
                ("correction", row["trailer_records_correction"]),
                ("marketing", row["candidate_has_marketing"]),
                ("safety", row["candidate_has_safety"]),
                ("short", row["candidate_too_short"]),
                ("done", row["already_curated"]),
            )
            if on
        )
        candidate = (row["candidate"] or "—").replace("|", "\\|")
        if len(candidate) > 160:
            candidate = candidate[:157] + "…"
        lines.append(
            f"| {row['reach_rank']} | `{row['parent']}` / `{row['form']}` "
            f"| {row['products']} | {row['renders_as']} | {flags or '—'} | {candidate} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche", type=int, default=100)
    args = parser.parse_args()

    rows = build_rows(args.tranche)
    json_path = OUT_DIR / "form_note_curation_latest.json"
    md_path = OUT_DIR / "form_note_curation_latest.md"
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_markdown(rows, args.tranche, md_path)

    flagged = sum(
        1
        for r in rows
        if r["tranche_1"]
        and (
            r["trailer_records_correction"]
            or r["candidate_has_marketing"]
            or r["candidate_has_safety"]
            or r["candidate_too_short"]
        )
    )
    print(f"{len(rows)} forms in catalog; tranche 1 = {args.tranche}")
    print(f"flagged for close review inside tranche 1: {flagged}")
    print(f"wrote {md_path.name} and {json_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
