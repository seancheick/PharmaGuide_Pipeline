#!/usr/bin/env python3
"""Generate WAVE2_DEEP_CURATION.md from the per-identity determination files.

Every number comes from an artefact: the determinations, the measured reach
projection, and the wave's own prescreen. Nothing in this report is typed twice.

    python3 scripts/audits/evidence_expansion_2026_09/build_deep_curation_report.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ORDER = ["propose", "propose_high_risk", "ready_but_blocked_upstream", "hold_null_semantics",
         "hold_and_handoff", "hold_integrity", "hold", "reclassify_handoff", "no_qualifying"]
LABEL = {
    "propose": "propose for approval",
    "propose_high_risk": "propose - HIGH RISK, needs a human decision",
    "ready_but_blocked_upstream": "evidence ready, blocked upstream",
    "hold_null_semantics": "hold - blocked only by the null decision",
    "hold_and_handoff": "hold + route to another owner",
    "hold_integrity": "hold - integrity check outstanding",
    "hold": "hold",
    "reclassify_handoff": "not efficacy - route to another owner",
    "no_qualifying": "no qualifying evidence",
}


def main() -> int:
    dets = [json.loads(p.read_text())
            for p in sorted((OUT / "wave2_determinations").glob("*.json"))]
    reach = json.loads((OUT / "wave2_projected_reach.json").read_text())["identities"]
    pre = {i["canonical_id"]: i for i in json.loads((OUT / "wave2_prescreen.json").read_text())["identities"]}
    by_action = collections.defaultdict(list)
    for d in dets:
        by_action[d["action"]].append(d)

    reached = sum(reach[c]["evidence_zero_products_the_record_would_reach"]
                  for c in reach if c in {d["canonical_id"] for d in by_action["propose"]}
                  | {d["canonical_id"] for d in by_action["propose_high_risk"]})
    blocked = sum(pre[d["canonical_id"]]["catalog"]["evidence_zero_products"]
                  for d in by_action["ready_but_blocked_upstream"])

    lines = [
        "# Wave 2 deep curation — all 25 curate identities read centrally (2026-09-18)",
        "",
        "Every identity screening marked `curate` was re-read source by source against the live-verified",
        "abstracts, with the catalog's measured label doses and resolved forms beside them. **Nothing was",
        "authored into the registry, no score moved, no catalog rebuilt.** These are proposals.",
        "",
        "## Outcome",
        "",
        "| outcome | identities | Evidence=0 products |", "|---|---:|---:|",
    ]
    for action in ORDER:
        rows = by_action.get(action) or []
        if not rows:
            continue
        ev0 = sum(pre[d["canonical_id"]]["catalog"]["evidence_zero_products"] for d in rows)
        lines.append(f"| {LABEL[action]} | {len(rows)} | {ev0} |")
    lines += [f"| **total** | **{len(dets)}** | "
              f"**{sum(pre[d['canonical_id']]['catalog']['evidence_zero_products'] for d in dets)}** |", "",
              f"The records proposed for approval would reach **{reached} products that sit at Evidence 0 today** "
              f"(measured, `project_record_reach.py`). A further **{blocked}** are unreachable for a reason that "
              "has nothing to do with evidence — see below.", ""]

    lines += ["## Measured reach of each proposed record", "",
              "| identity | dose floor | products carrying it | record would apply to | below floor / undosed | Evidence=0 reached |",
              "|---|---:|---:|---:|---:|---:|"]
    for canonical, row in reach.items():
        floor = row["proposed_min_daily_dose_mg"]
        lines.append(
            f"| `{canonical}` | {str(floor) + ' mg' if floor else 'none (cranberry precedent)'} | "
            f"{row['products_carrying_the_identity']} | {row['products_the_record_would_apply_to']} | "
            f"{row['products_below_the_dose_floor_or_undosed']} | "
            f"{row['evidence_zero_products_the_record_would_reach']} |")
    lines.append("")

    for action in ORDER:
        rows = by_action.get(action) or []
        if not rows:
            continue
        lines += [f"## {LABEL[action]}", ""]
        for d in sorted(rows, key=lambda r: -pre[r["canonical_id"]]["catalog"]["evidence_zero_products"]):
            cat = pre[d["canonical_id"]]["catalog"]
            head = (f"**`{d['canonical_id']}`** — {cat['products']} products, {cat['evidence_zero_products']} "
                    f"at Evidence 0")
            bits = []
            if d.get("direction"):
                bits.append(f"direction **{d['direction']}**")
            if d.get("study_type"):
                bits.append(f"`{d['study_type']}`")
            if d.get("sources"):
                bits.append("PMIDs " + ", ".join(d["sources"]))
            if d.get("label_median_mg") is not None:
                bits.append(f"label median {d['label_median_mg']:g} mg")
            if d.get("studied_dose"):
                bits.append(f"studied {d['studied_dose']}")
            lines += [head + (" — " + "; ".join(bits) if bits else ""), "", d["note"], ""]

    (OUT / "WAVE2_DEEP_CURATION.md").write_text("\n".join(lines) + "\n")
    print(f"determinations {len(dets)}; " + " ".join(f"{a}={len(by_action[a])}" for a in ORDER if by_action[a]))
    print(f"Evidence=0 reached by proposals: {reached}; blocked upstream: {blocked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
