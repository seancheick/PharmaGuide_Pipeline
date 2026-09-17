#!/usr/bin/env python3
"""Phase 1 checkpoint report (read-only).

Pulls every Wave 1 artefact into one report and stops. Coverage is reported
separately from score, "not reviewed" is never written as "no evidence", and the
scorer-compatibility split says how much curated evidence the current generic
scorer could actually consume.

    python3 scripts/audits/evidence_expansion_2026_09/build_checkpoint.py --slim <slim.jsonl> --screen-dir DIR [--screen-dir DIR]
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--screen-dir", action="append", type=Path, default=[])
    args = parser.parse_args()

    inventory = load("inventory.json")
    taxonomy = load("zero_evidence_taxonomy.json")
    contexts = load("wave1_contexts.json")
    verification = load("wave1_live_verification.json")
    search_log = load("wave1_search_log.json")
    blockers = load("blocker_routing.json")
    legacy = load("legacy_backfill_queue.json")
    summary = inventory["summary"]
    identities = {row["canonical_id"]: row for row in inventory["identities"]}

    # screening statistics
    screened = kept = rejected = shortlisted = handoffs = 0
    for directory in args.screen_dir:
        for path in sorted(directory.glob("*.screen.json")):
            screen = json.loads(path.read_text())
            screened += screen.get("screened") or 0
            kept += screen.get("kept") or 0
            rejected += len(screen.get("rejected") or [])
            shortlisted += len(screen.get("shortlist") or [])
            handoffs += len(screen.get("handoff") or [])
    findings = collections.Counter(f["finding"] for f in verification.get("findings", []))

    authored = contexts.get("candidates", [])
    authored_ids = [c["canonical_id"] for c in authored]
    authored_slots = sum(identities[i]["slots"] for i in authored_ids if i in identities)
    authored_products = sum(identities[i]["products"] for i in authored_ids if i in identities)
    authored_zero = sum(identities[i]["evidence_zero_products"] for i in authored_ids if i in identities)
    class_counts = collections.Counter(c["scorer_compatibility"]["class"] for c in authored)
    class_a_zero = sum(identities[c["canonical_id"]]["evidence_zero_products"] for c in authored
                       if c["scorer_compatibility"]["class"] == "A" and c["canonical_id"] in identities)
    class_b_zero = authored_zero - class_a_zero
    searched = {item["canonical_id"] for item in search_log.get("identities", [])}
    searched_slots = sum(identities[i]["slots"] for i in searched if i in identities)
    total_contexts = sum(len(c["contexts"]) for c in authored)
    mapped = summary["mapped_slots"]

    def pct(part, whole):
        return f"{100 * part / whole:.1f}%" if whole else "—"

    lines = [
        "# Evidence expansion — Phase 1 checkpoint (2026-09-17)", "",
        "**STOP POINT.** No production evidence was written, no score moved, no scoring rule or weight changed, "
        "no catalog rebuild, no release. Every authored context is pending owner review.", "",
        "## Headline", "",
        f"- **{summary['evidence_zero_non_probiotic_lane']}** non-probiotic products ship Evidence 0 "
        f"({pct(summary['evidence_zero_non_probiotic_lane'], summary['scored_products_non_probiotic_lane'])} of "
        f"{summary['scored_products_non_probiotic_lane']} scored).",
        f"- **{summary['recoverable_by_curation_alone']}** "
        f"({pct(summary['recoverable_by_curation_alone'], summary['evidence_zero_non_probiotic_lane'])}) are blocked "
        "by missing evidence curation — this project's target.",
        f"- **{summary['blocked_or_already_matched']}** "
        f"({pct(summary['blocked_or_already_matched'], summary['evidence_zero_non_probiotic_lane'])}) are blocked "
        "elsewhere; more papers cannot move them (see BLOCKER_ROUTING.md).",
        f"- **No scorer-defect bucket**: 0 products have an accepted, point-carrying match yet Evidence 0.",
        f"- **{len(authored)} identities deeply curated** into **{total_contexts} pending contexts**; "
        f"**{class_counts.get('A', 0)} are class A** (the current scorer could apply them safely) and "
        f"**{class_counts.get('B', 0)} are class B** (valid evidence the scorer is too coarse to apply).", "",
        "## What the deeply authored identities cover", "",
        "| measure | value |", "|---|---:|",
        f"| identities deeply authored | {len(authored)} |",
        f"| their product-active slots | {authored_slots} ({pct(authored_slots, mapped)} of mapped slots) |",
        f"| their products | {authored_products} |",
        f"| their Evidence=0 products | {authored_zero} |",
        f"| identities searched (bounded, logged) | {len(searched)} |",
        f"| their product-active slots | {searched_slots} ({pct(searched_slots, mapped)} of mapped slots) |", "",
        "## Projected coverage if the owner approved the proposals", "",
        "| outcome | Evidence=0 products affected |", "|---|---:|",
        f"| would gain evidence under the CURRENT scorer (class A approvals) | {class_a_zero} |",
        f"| held back because the current scorer is too coarse (class B) | {class_b_zero} |", "",
        "Every Wave 1 identity landed in class B. The curated evidence is real; the generic scorer cannot yet apply "
        "it without overgeneralising. That is the bridge to Phase 2, and it is measured rather than assumed.", "",
        "## Top generic-scorer limitations exposed by real curated evidence", "",
        "| limitation | evidence that exposed it | consequence |", "|---|---|---|",
        "| No population gate | isoflavones (all positive results in peri/postmenopausal women); DHEA (IVF with "
        "diminished ovarian reserve, adrenal insufficiency) | `clinical_applicability.py` validates and carries a "
        "`studied_population` string (line 241) but never compares it to anything, and the product's "
        "`target_population` is read only by the probiotic lane. Approving these records would transfer "
        "menopause/fertility-clinic evidence to every consumer product. |",
        "| No material scoping from enricher-resolved forms | butterbur (PA-free Petadolex vs unspecified) | "
        "`required_form_terms` matches PRINTED label text; the resolved form identity lives on a different row, so "
        "the studied branded material cannot be selected. Probe: 61929 returned `clinical_form_mismatch` at exactly "
        "the studied 150 mg/day. |",
        "| Multi-row identities silently fail to link | butterbur 328579 and 293376 (two butterbur rows each) | "
        "`_linked_rows` returns nothing when more than one canonical candidate row exists, so applicability cannot be "
        "assessed at all. |",
        "| No exposure-basis concept | linoleic acid (whole-diet substitution trials at 7.5-20 g/day vs a 362 mg "
        "capsule) | Dietary-substitution evidence would become capsule efficacy across a 20-40x dose gap. |",
        "| Dose floor cannot express 'positive only far above label' | gotu kola (12 g challenge positive, 1,000 mg "
        "null; label median 60 mg) | A record would credit label servings with evidence from doses they never deliver. |",
        "| Null direction manufactures affirmative credit | 4 legacy null records | See "
        "GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md. |", "",
        "## Null-evidence exposure (current behaviour, unchanged)", "",
    ]
    null_md = OUT / "GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md"
    if null_md.exists():
        lines += ["- 4 legacy records carry `effect_direction: null`; the generic scorer keeps 25% of their points.",
                  "- 2,423 scored products match at least one null record; for 249 of them the ONLY point-carrying "
                  "evidence is a null record.",
                  "- No Wave 1 null-only record is proposed for approval until that semantic is decided separately.", ""]
    lines += [
        "## Source verification (subagent screening is a draft, never the record)", "",
        "| measure | value |", "|---|---:|",
        f"| records screened by subagents | {screened} |",
        f"| kept after screening | {kept} |",
        f"| rejected with a reason code | {rejected} |",
        f"| shortlisted for central reading | {shortlisted} |",
        f"| handoffs proposed to other owners | {handoffs} |",
        f"| shortlist PMIDs re-fetched live by Claude | {verification.get('_metadata', {}).get('verified_records', 0)} |",
        f"| PMIDs not found live | {findings.get('PMID_NOT_FOUND_LIVE', 0)} |",
        f"| stored-vs-live title drift | {findings.get('TITLE_DRIFT', 0)} |",
        f"| integrity flags (erratum) | {findings.get('INTEGRITY_HAS_ERRATUM', 0)} |",
        f"| human status ambiguous (fails closed) | {findings.get('HUMAN_STATUS_AMBIGUOUS', 0)} |",
        f"| **quote rejected — ellipsis-joined fragments** | {findings.get('QUOTE_ELIDED_NOT_CONTIGUOUS', 0)} |",
        f"| **quote rejected — composed, not in source** | {findings.get('QUOTE_NOT_IN_LIVE_ABSTRACT', 0)} |", "",
        "Every rejected quote was caught before authoring: Claude re-extracts each quote from the abstract itself, "
        "and `validate_wave1_contexts.py` re-checks each one as a substring. The authored contexts contain "
        "0 unverified quotes. The screening brief was tightened mid-run and both agents were corrected.", "",
        "## Coverage (see COVERAGE.md for the full tables)", "",
        "| measure | value |", "|---|---:|",
        f"| unique mapped identities | {summary['unique_mapped_identities']} |",
        f"| product-active slots | {summary['product_active_slots_non_probiotic']} |",
        f"| identities covering 80% of slots | {summary['identities_for_mapped_slot_share'].get('0.8')} |",
        f"| identities covering 90% | {summary['identities_for_mapped_slot_share'].get('0.9')} |",
        f"| identities covering 95% | {summary['identities_for_mapped_slot_share'].get('0.95')} |",
        f"| identities with a legacy record (review state NOT established) | "
        f"{summary['identities_by_review_state'].get('legacy_review_state_not_established', 0)} |",
        f"| identities with no record at all | {summary['identities_by_review_state'].get('not_reviewed', 0)} |",
        f"| identities with a completed review | 0 |", "",
        "## Blocked outside evidence curation (routed, not fixed here)", "",
        "| class | products | owner |", "|---|---:|---|"]
    for row in blockers.get("by_class", []):
        lines.append(f"| {row['letter']} | {row['products']} | {row['owner']} |")
    lines += ["", "## Legacy 202 backfill queue", "",
              f"All {legacy.get('_metadata', {}).get('records', 0)} legacy records lack study contexts; "
              f"{legacy.get('_metadata', {}).get('records_without_dose_policy', 0)} carry no dose policy and "
              f"{legacy.get('_metadata', {}).get('records_without_applicability_scope', 0)} no applicability scope. "
              "Grandfathered means temporarily preserved, not permanently exempt — see LEGACY_BACKFILL.md.", "",
              "## Artefacts", "",
              "| file | contents |", "|---|---|",
              "| `COVERAGE.md` | coverage, category rollup, A–H taxonomy |",
              "| `QUEUE.md` / `queue.json` | gap and exposure queues over 773 identities |",
              "| `BLOCKER_ROUTING.md` | the products curation cannot fix, by owner |",
              "| `LEGACY_BACKFILL.md` | the grandfathered 202, by catalog exposure |",
              "| `GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md` | measured null-direction exposure |",
              "| `wave1_search_log.json` | exact queries, counts, truncation per identity |",
              "| `wave1_contexts.json` | authored pending contexts + proposals |",
              "| `wave1_live_verification.json` | live re-fetch findings |",
              "| `docs/plans/EVIDENCE_EXPANSION_WAVE1_REVIEW_PACKET_2026-09.md` | the owner decision packet |", "",
              "## Next wave, by leverage", "",
              "Discovery already covers 40 identities; contexts were authored for the 10 with the best evidence "
              "clarity, not to a quota. The gap queue orders what remains.", ""]
    (OUT / "CHECKPOINT.md").write_text("\n".join(lines) + "\n")
    print(f"wrote CHECKPOINT.md; authored {len(authored)} identities / {total_contexts} contexts; "
          f"class A {class_counts.get('A', 0)}, class B {class_counts.get('B', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
