#!/usr/bin/env python3
"""Render COVERAGE.md from inventory.json + zero_evidence_taxonomy.json (read-only).

Coverage is reported separately from score, and review completeness is never
implied from an evidence record existing: the 202 legacy records carry no review
state, so their slots are ``legacy_review_state_not_established``.

    python3 scripts/audits/evidence_expansion_2026_09/write_coverage_report.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
STATE_LABEL = {"not_reviewed": "not reviewed (no record)",
               "legacy_review_state_not_established": "legacy record, review state not established",
               "reviewed_no_qualifying_evidence_in_documented_scope": "reviewed, no qualifying evidence in scope"}
LETTER = {
    "A": "identity not reviewed — no evidence record exists",
    "B": "identity reviewed, no qualifying evidence in the documented scope",
    "C": "identity / form / linkage unresolved",
    "D": "dose applicability unresolved or outside scope",
    "E": "evidence matched but carries no efficacy credit (null/negative/reference-only)",
    "F": "formula- or combination-only evidence",
    "G": "accepted match with points yet Evidence 0 — scorer defect candidate",
    "H": "no active row the scorer can use (label actives demoted upstream)",
}


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "—"


def main() -> int:
    inventory = json.loads((OUT / "inventory.json").read_text())
    taxonomy = json.loads((OUT / "zero_evidence_taxonomy.json").read_text())
    s = inventory["summary"]
    identities = inventory["identities"]
    mapped = s["mapped_slots"]

    lines = [
        "# Evidence coverage — non-probiotic lane (Phase 1 baseline)", "",
        f"Built from the corpus re-enriched and re-scored 2026-09-17 ({s['scored_products']} scored products; "
        f"the probiotic lane has its own registry and queue and is excluded except where stated).", "",
        "Three columns are kept apart: **evidence strength**, **applicability**, **review completeness**. "
        "No non-probiotic identity has a completed review today, so every identity is either "
        "`not reviewed` or `legacy record, review state not established`. "
        "\"Legacy record\" is not \"reviewed\".", "",
        "## Catalog", "",
        f"| scored products | {s['scored_products']} |", "|---|---:|",
        f"| non-probiotic lane | {s['scored_products_non_probiotic_lane']} |",
        f"| product-active slots (non-probiotic) | {s['product_active_slots_non_probiotic']} |",
        f"| unique mapped identities | {s['unique_mapped_identities']} |",
        f"| Evidence = 0 products (non-probiotic) | {s['evidence_zero_non_probiotic_lane']} "
        f"({pct(s['evidence_zero_non_probiotic_lane'], s['scored_products_non_probiotic_lane'])}) |",
        f"| Evidence = 0 products (probiotic lane) | {s['evidence_zero_probiotic_lane']} |",
        f"| legacy registry entries | {s['legacy_registry_entries']} |",
        f"| documented bounded reviews | {s['documented_bounded_reviews']} |", "",
        "## Review coverage", "",
        "| review state | identities | mapped slots | share of slots |", "|---|---:|---:|---:|",
    ]
    for state, slots in sorted(s["mapped_slots_by_review_state"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {STATE_LABEL[state]} | {s['identities_by_review_state'].get(state, 0)} | {slots} | "
                     f"{pct(slots, mapped)} |")
    cuts = s["identities_for_mapped_slot_share"]
    lines += ["", "### How many identities cover the catalog", "",
              "| share of mapped product-active slots | identities needed |", "|---|---:|"]
    for cut, count in sorted(cuts.items()):
        lines.append(f"| {float(cut):.0%} | {count} |")
    lines += ["", f"Measured from the corpus, not assumed: the top {cuts.get('0.8', '—')} identities cover 80% of "
              "mapped slots, and the long tail beyond "
              f"{cuts.get('0.95', '—')} covers the last 5%.", ""]

    lines += ["## Category rollup (mapped slots by review state)", "",
              "| category | slots | not reviewed | legacy record | reviewed |", "|---|---:|---:|---:|---:|"]
    for category, states in sorted(inventory["category_rollup"].items(),
                                   key=lambda kv: -sum(kv[1].values())):
        total = sum(states.values())
        lines.append(f"| {category} | {total} | {pct(states.get('not_reviewed', 0), total)} | "
                     f"{pct(states.get('legacy_review_state_not_established', 0), total)} | "
                     f"{pct(states.get('reviewed_no_qualifying_evidence_in_documented_scope', 0), total)} |")

    lines += ["", "## Why Evidence = 0 (A–H taxonomy)", "",
              f"{s['evidence_zero_non_probiotic_lane']} products, classified through the production match seam. "
              "Every applicable reason is kept; the table shows the primary one.", "",
              "| letter | meaning | products |", "|---|---|---:|"]
    for letter, count in s["taxonomy_primary"].items():
        lines.append(f"| {letter} | {LETTER[letter]} | {count} |")
    lines += ["", "### Sub-reasons", "", "| detail | products |", "|---|---:|"]
    for detail, count in s["taxonomy_detail_counts"].items():
        lines.append(f"| `{detail}` | {count} |")

    lines += ["", "## Bottleneck: what evidence curation alone can move", "",
              f"- **{s['recoverable_by_curation_alone']}** of the {s['evidence_zero_non_probiotic_lane']} "
              f"({pct(s['recoverable_by_curation_alone'], s['evidence_zero_non_probiotic_lane'])}) have a mapped, "
              "dose-bearing active with no evidence record at all — curation is the blocker.",
              f"- **{s['blocked_or_already_matched']}** "
              f"({pct(s['blocked_or_already_matched'], s['evidence_zero_non_probiotic_lane'])}) are blocked elsewhere: "
              "the label's actives were demoted upstream, the identity or form is unresolved, the record is "
              "formula-scoped, or a matched record carries no efficacy credit. More literature will not move these.",
              "", "Identities blocking the most Evidence=0 products:", "",
              "| identity | Evidence=0 products | review state | blocker |", "|---|---:|---|---|"]
    blockers = collections.Counter()
    for product in taxonomy["products"]:
        for canonical in product["active_canonicals"]:
            blockers[canonical] += 1
    by_id = {row["canonical_id"]: row for row in identities}
    for canonical, count in blockers.most_common(15):
        row = by_id.get(canonical, {})
        state = STATE_LABEL.get(row.get("review_state", ""), "unmapped / not in inventory")
        blocker = "evidence curation" if row.get("review_state") == "not_reviewed" else \
            "record exists — check identity/form/dose" if row else "identity normalization"
        lines.append(f"| `{canonical}` | {count} | {state} | {blocker} |")

    lines += ["", "## Source coverage of the legacy records", "",
              "Legacy records are counted by what they claim, not by a completed review:", ""]
    study_types = collections.Counter()
    directions = collections.Counter()
    registry = json.loads((OUT.parents[1] / "data/backed_clinical_studies.json").read_text())
    for entry in registry["backed_clinical_studies"]:
        study_types[entry.get("study_type")] += 1
        directions[entry.get("effect_direction")] += 1
    lines += ["| study_type | records |", "|---|---:|"] + \
             [f"| {k} | {v} |" for k, v in study_types.most_common()] + \
             ["", "| effect_direction | records |", "|---|---:|"] + \
             [f"| {k} | {v} |" for k, v in directions.most_common()]

    (OUT / "COVERAGE.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT / 'COVERAGE.md'} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
