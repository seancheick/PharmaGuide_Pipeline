#!/usr/bin/env python3
"""Wave 2 owner packet and checkpoint metrics, generated from the wave's artefacts.

The headline metric is deliberately NOT the number of newly approvable records.
It is how many Evidence=0 products now have an honest, source-verified reason for
their state - supported, null, no qualifying evidence, or held with a named
blocker. A product whose zero is explained is a product the app can talk about.

    python3 scripts/audits/evidence_expansion_2026_09/build_wave2_packet.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ACTION_TO_PROPOSAL = {
    "applied_approved": "APPROVED + APPLIED",
    "reviewed_supportive_hold": "REVIEWED SUPPORTIVE, scoring HELD",
    "applied_reviewed_null": "APPLIED as reviewed NULL (earns nothing)",
    "propose": "APPROVE",
    "propose_high_risk": "APPROVE (high risk - human decision)",
    "ready_but_blocked_upstream": "HOLD (blocked upstream, not by evidence)",
    "hold_null_semantics": "HOLD (null direction; parked decision)",
    "hold_and_handoff": "HOLD + HANDOFF",
    "hold_integrity": "HOLD (integrity)",
    "hold": "HOLD",
    "reclassify_handoff": "HANDOFF",
    "no_qualifying": "REVIEWED_NO_QUALIFYING",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()

    pre = json.loads((OUT / "wave2_prescreen.json").read_text())
    pre_by = {i["canonical_id"]: i for i in pre["identities"]}
    reach = json.loads((OUT / "wave2_projected_reach.json").read_text())["identities"]
    ctxs = json.loads((OUT / "wave2_contexts.json").read_text())
    dets = {p.stem: json.loads(p.read_text())
            for p in sorted((OUT / "wave2_determinations").glob("*.json"))}
    screens = {i["canonical_id"]: i for i in pre["identities"]}

    reviewed = set(pre_by)                       # every identity this wave touched
    ctx_counts = collections.Counter()
    for identity, rows in ctxs["contexts_by_identity"].items():
        ctx_counts[identity] += len(rows)
    for row in ctxs["syntheses_recorded_as_references"]:
        ctx_counts[row["components"][0]] += 0    # references are not contexts

    # ---- the real expansion metric, measured over the scored corpus ----
    zero_products = 0
    zero_fully_reviewed = 0
    zero_partly_reviewed = 0
    for line in args.slim.open():
        product = json.loads(line)
        if (product.get("evidence") or 0) != 0:
            continue
        zero_products += 1
        identities = {row.get("canonical_id") for row in product["rows"]
                      if row.get("role_classification") == "active_scorable" and row.get("canonical_id")}
        if not identities:
            continue
        touched = identities & reviewed
        if touched and touched == identities:
            zero_fully_reviewed += 1
        elif touched:
            zero_partly_reviewed += 1

    rows = []
    for canonical, det in dets.items():
        cat = pre_by[canonical]["catalog"]
        r = reach.get(canonical, {})
        rows.append({
            "identity": canonical,
            "products": cat["products"], "evidence_zero": cat["evidence_zero_products"],
            "contexts_authored": ctx_counts.get(canonical, 0),
            "direction": det.get("direction", "-"),
            "dose_applicability": ("floor " + str(r["proposed_min_daily_dose_mg"]) + " mg"
                                   if r.get("proposed_min_daily_dose_mg") else
                                   ("no dose policy" if canonical in reach else
                                    det.get("studied_dose", "-"))),
            "proposal": ACTION_TO_PROPOSAL[det["action"]],
            "projected_products": r.get("evidence_zero_products_the_record_would_reach", 0),
            "high_risk": "yes" if det["action"] == "propose_high_risk" or "handoff" in det["action"] else "",
            "reason": det["note"],
        })
    rows.sort(key=lambda r: (list(ACTION_TO_PROPOSAL.values()).index(r["proposal"]), -r["evidence_zero"]))

    by_proposal = collections.Counter(r["proposal"] for r in rows)
    lines = [
        "# Wave 2 owner packet — 50 identities searched, 25 deeply curated (2026-09-18)",
        "",
        "**No production evidence write, no score movement, no catalog rebuild, no release.** Contexts are",
        "authored as `source_verified_pending_clinical_review` and validated with `authoring=True`, which",
        "refuses any other status. Approval is the owner's act.",
        "",
        "## The expansion metric",
        "",
        "Not the number of newly approvable records — the number of zeroes that now have an honest reason.",
        "",
        "| measure | value |", "|---|---:|",
        f"| identities searched | {len(pre_by)} |",
        f"| identities deeply curated (read source by source) | {len(dets)} |",
        f"| study contexts authored and validated | {ctxs['_metadata']['contexts']} |",
        f"| syntheses recorded as verified references (no dose stated) | {ctxs['_metadata']['syntheses_recorded_as_references']} |",
        f"| context validation failures | {ctxs['_metadata']['validation_failures']} |",
        f"| Evidence=0 products in the wave's identities | {sum(i['catalog']['evidence_zero_products'] for i in pre_by.values())} |",
        f"| Evidence=0 products this wave alone fully reviewed | {zero_fully_reviewed} |",
        f"| ... with at least one identity reviewed by this wave | {zero_partly_reviewed} |",
        "",
        "Cumulative coverage, and the distinction between the three numbers, is owned by",
        "`COVERAGE_MANIFEST.json` and pinned to a corpus snapshot - this packet does not restate it in its",
        "own words. Snapshot: git `{git_head}`, {snapshot_products} scored products, {snapshot_zero} at",
        "Evidence 0.",
        "",
        "| cumulative metric | products | share of the pinned {snapshot_zero} |", "|---|---:|---:|",
        "| review state established (supported / null / held / no-qualifying / handoff) | "
        "**{review_state}** | **{review_state_pct}%** |",
        "| deep curated (read centrally, source by source) | {deep} | {deep_pct}% |",
        "| score reachable by an APPROVED scoring record | {reachable} | - |",
        "",
        "## Decision table",
        "",
        "| identity | products | Ev=0 | contexts | direction | dose applicability | proposal | projected products | high risk |",
        "|---|---:|---:|---:|---|---|---|---:|:--:|",
    ]
    for r in rows:
        lines.append(f"| `{r['identity']}` | {r['products']} | {r['evidence_zero']} | {r['contexts_authored']} | "
                     f"{r['direction']} | {r['dose_applicability']} | {r['proposal']} | "
                     f"{r['projected_products']} | {r['high_risk']} |")
    lines += ["", "## Proposal rollup", "", "| proposal | identities | Evidence=0 products |", "|---|---:|---:|"]
    for proposal, count in by_proposal.most_common():
        ev0 = sum(r["evidence_zero"] for r in rows if r["proposal"] == proposal)
        lines.append(f"| {proposal} | {count} | {ev0} |")
    lines += ["", "## Reasons", ""]
    for r in rows:
        lines += [f"**`{r['identity']}`** — {r['proposal']}", "", r["reason"], ""]

    manifest = json.loads((OUT / "COVERAGE_MANIFEST.json").read_text())
    zero_stats = manifest["products_at_evidence_zero"]
    body = "\n".join(lines).format(
        git_head=manifest["corpus_manifest"]["git_head"][:12],
        snapshot_products=manifest["corpus_manifest"]["scored_products_in_snapshot"],
        snapshot_zero=zero_stats["total"],
        review_state=zero_stats["review_state_established"],
        review_state_pct=zero_stats["review_state_established_pct"],
        deep=zero_stats["deep_curated"], deep_pct=zero_stats["deep_curated_pct"],
        reachable=zero_stats["score_reachable_by_an_approved_record"])
    (OUT / "WAVE2_OWNER_PACKET.md").write_text(body + "\n")
    print(json.dumps({"identities": len(rows), "contexts": ctxs["_metadata"]["contexts"],
                      "evidence_zero_products_corpus": zero_products,
                      "fully_reviewed": zero_fully_reviewed, "partly_reviewed": zero_partly_reviewed,
                      "by_proposal": dict(by_proposal)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
