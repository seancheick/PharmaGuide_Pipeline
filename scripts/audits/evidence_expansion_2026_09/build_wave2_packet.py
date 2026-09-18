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
        f"| scored products at Evidence 0 in the whole corpus | {zero_products} |",
        f"| ... whose every scorable identity is now reviewed | **{zero_fully_reviewed}** |",
        f"| ... with at least one identity now reviewed | {zero_partly_reviewed} |",
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

    (OUT / "WAVE2_OWNER_PACKET.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"identities": len(rows), "contexts": ctxs["_metadata"]["contexts"],
                      "evidence_zero_products_corpus": zero_products,
                      "fully_reviewed": zero_fully_reviewed, "partly_reviewed": zero_partly_reviewed,
                      "by_proposal": dict(by_proposal)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
