#!/usr/bin/env python3
"""Pinned coverage metrics for the evidence expansion (read-only).

Three different numbers were being called the same thing, and the denominator
moved between runs. This pins both:

  * REVIEW STATE ESTABLISHED - every scorable identity on the product has a
    completed review outcome (supported / null / held / no-qualifying / handoff).
    A screening-stage HOLD counts: the product's zero is explained.
  * DEEP CURATED - the product's identities were read centrally, source by
    source, not just screened.
  * SCORE REACHABLE - the product would actually receive an APPROVED, scoring
    record after the applicability and dose gates. Reference-tier and
    null-direction records are reviewed but score nothing, so they are excluded
    here by design.

Every report carries the corpus manifest: git HEAD, the slim snapshot's sha256,
its product count and its build date. Percentages that move must be explained by
a new snapshot, not by drift.

    python3 scripts/audits/evidence_expansion_2026_09/build_coverage_manifest.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]

# Identities whose evidence was read centrally, source by source.
WAVE1_DEEP = {"butterbur", "ginkgo", "isoflavones", "dhea", "gotu_kola", "linoleic_acid",
              "tribulus", "horny_goat_weed", "dandelion", "d_ribose"}
LEGACY_REPAIRED = {"vitamin_b12_cobalamin", "saw_palmetto", "diindolylmethane", "boron"}
# Records that are approved AND score. Reference-tier and null records are reviewed
# but contribute nothing, so they never appear here.
# amla was held at reference tier on 2026-09-18, so it no longer reaches any score.
SCORING_APPROVED = {"common_bean_extract": 1000}


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()

    pre = json.loads((OUT / "wave2_prescreen.json").read_text())
    wave2_all = {i["canonical_id"] for i in pre["identities"]}
    wave2_deep = {p.stem for p in (OUT / "wave2_determinations").glob("*.json")}
    reviewed = wave2_all | WAVE1_DEEP | LEGACY_REPAIRED
    deep = wave2_deep | WAVE1_DEEP | LEGACY_REPAIRED

    digest = hashlib.sha256(args.slim.read_bytes()).hexdigest()
    MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}

    scored = zero = 0
    review_state = deep_cov = reachable = partial = 0
    for line in args.slim.open():
        product = json.loads(line)
        scored += 1
        if (product.get("evidence") or 0) != 0:
            continue
        zero += 1
        identities = {row.get("canonical_id") for row in product["rows"]
                      if row.get("role_classification") == "active_scorable" and row.get("canonical_id")}
        if not identities:
            continue
        if identities <= reviewed:
            review_state += 1
        elif identities & reviewed:
            partial += 1
        if identities <= deep:
            deep_cov += 1
        for canonical, floor in SCORING_APPROVED.items():
            if canonical not in identities:
                continue
            best = 0.0
            for row in product["rows"]:
                if row.get("canonical_id") != canonical or row.get("role_classification") != "active_scorable":
                    continue
                scale = MG.get(str(row.get("unit_normalized") or "").lower())
                value = row.get("quantity")
                if scale and isinstance(value, (int, float)) and value > 0:
                    best = max(best, value * scale)
            if best >= floor:
                reachable += 1
                break

    payload = {
        "corpus_manifest": {
            "git_head": git_head(),
            "slim_snapshot_sha256": digest,
            "slim_snapshot_path": str(args.slim),
            "scored_products_in_snapshot": scored,
            "evidence_zero_products_in_snapshot": zero,
            "generated": dt.date.today().isoformat(),
            "regenerate_with": "python3 scripts/audits/evidence_expansion_2026_09/extract_corpus.py "
                               "(rebuilds the slim snapshot from scripts/products/output_*_scored)",
            "note": "Pin every coverage percentage to this manifest. A different product count means a "
                    "different snapshot, not progress.",
        },
        "identities": {
            "review_state_established": len(reviewed),
            "deep_curated": len(deep),
            "wave2_searched": len(wave2_all),
            "wave2_deep_curated": len(wave2_deep),
            "scoring_approved": sorted(SCORING_APPROVED),
        },
        "products_at_evidence_zero": {
            "total": zero,
            "review_state_established": review_state,
            "review_state_established_pct": round(100 * review_state / zero, 1) if zero else 0,
            "deep_curated": deep_cov,
            "deep_curated_pct": round(100 * deep_cov / zero, 1) if zero else 0,
            "partially_reviewed": partial,
            "score_reachable_by_an_approved_record": reachable,
        },
    }
    (OUT / "COVERAGE_MANIFEST.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
