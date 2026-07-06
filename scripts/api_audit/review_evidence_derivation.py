#!/usr/bin/env python3
"""Preview the SP-6 evidence-strength derivation for curated PAIRWISE
interactions — the CLINICIAN REVIEW artifact for the interaction_db
`evidence_level` backfill (the shipped DB has 150/150 NULL).

Read-only. Applies verify_interactions.derive_evidence_level to every curated
interaction and reports the proposed grade plus the inputs that drove it. It
does NOT modify data or rebuild anything. Review the grades, adjust the rubric
TABLES in verify_interactions.py if needed, then rebuild.

    python3 scripts/api_audit/review_evidence_derivation.py            # summary + flags
    python3 scripts/api_audit/review_evidence_derivation.py --out FILE # also write a markdown table
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from verify_interactions import derive_evidence_level  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent
CURATED_GLOB = str(SCRIPTS / "data" / "curated_interactions" / "*.json")
TIERS = ("established", "probable", "moderate", "limited", "theoretical", "no_data")
SERIOUS_SEVERITIES = {"contraindicated", "avoid", "major"}
BELOW_PROBABLE = {"moderate", "limited", "theoretical", "no_data"}


def _rows():
    for path in sorted(glob.glob(CURATED_GLOB)):
        data = json.loads(Path(path).read_text())
        entries = data.get("interactions") if isinstance(data, dict) else data
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            pmids = e.get("source_pmids") or []
            yield {
                "id": e.get("id", ""),
                "severity": e.get("severity", ""),
                "agents": f"{e.get('agent1_name', '?')} x {e.get('agent2_name', '?')}",
                "confidence": e.get("clinical_confidence", ""),
                "basis": e.get("evidence_basis", ""),
                "pmids": len(pmids),
                "proposed": derive_evidence_level(
                    e.get("evidence_basis"), e.get("clinical_confidence"), pmids
                ),
            }


def serious_below_probable_flags(rows):
    """Rows a clinician should eyeball before rebuild.

    Pairwise curated interactions use legacy severity labels (`Major`,
    `Moderate`, `Minor`, `Contraindicated`), not just app severities such as
    `avoid`. A serious row below `probable` may still be clinically correct,
    but it must not be hidden by the review artifact.
    """
    return [
        r
        for r in rows
        if str(r.get("severity", "")).strip().lower() in SERIOUS_SEVERITIES
        and str(r.get("proposed", "")).strip().lower() in BELOW_PROBABLE
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write a full markdown table to this path")
    args = ap.parse_args()

    rows = list(_rows())
    dist = collections.Counter(r["proposed"] for r in rows)

    print(f"Curated pairwise interactions: {len(rows)}")
    print("\nProposed evidence_level distribution (currently ALL NULL):")
    for tier in TIERS:
        print(f"  {tier:12} {dist.get(tier, 0)}")

    # Cases a clinician should eyeball: serious severities below probable
    # evidence, and any 'no_data' (unknown/absent basis).
    flags = serious_below_probable_flags(rows)
    print(
        "\nReview flags — serious severity below probable evidence "
        f"({len(flags)}):"
    )
    for r in flags:
        print(
            f"  [{r['severity']} -> {r['proposed']}] {r['id']}: {r['agents']} "
            f"(conf={r['confidence']}, basis={r['basis']}, pmids={r['pmids']})"
        )
    nodata = [r for r in rows if r["proposed"] == "no_data"]
    if nodata:
        print(
            f"\nno_data (unknown/absent evidence_basis): {len(nodata)} -> "
            + ", ".join(r["id"] for r in nodata[:12])
        )

    if args.out:
        lines = [
            "| id | severity | agents | confidence | basis | pmids | proposed |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in sorted(rows, key=lambda x: (x["severity"], x["proposed"], x["id"])):
            lines.append(
                f"| {r['id']} | {r['severity']} | {r['agents']} | {r['confidence']} "
                f"| {r['basis']} | {r['pmids']} | **{r['proposed']}** |"
            )
        Path(args.out).write_text("\n".join(lines) + "\n")
        print(f"\nWrote {len(rows)}-row review table -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
