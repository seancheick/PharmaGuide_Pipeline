#!/usr/bin/env python3
"""v4 release-readiness audit.

This is the hard gate between "v4 scores run" and "v4 is safe to expose as a
shipping shadow/primary candidate." It classifies v3→v4 transitions on the
shipped universe and fails on the two states that should never reach users:

  - a v3 safety verdict downgraded by v4
  - a v3-scored shipped product that v4 refuses to score for anything other
    than no usable identity/evidence

It also records review queues for quality posture shifts (for example
POOR→SAFE) without making those safety blockers when the raw v4 rubric score
clears the SAFE threshold and v3's safety verdict was already SAFE.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import v4_full_corpus_delta as delta  # noqa: E402


DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_release_readiness"

SAFETY_RANK = {"BLOCKED": 4, "UNSAFE": 3, "CAUTION": 2, "POOR": 1, "SAFE": 0}

NO_USABLE_IDENTITY_FIELDS = {
    "product_payload",
    "active_identity",
    "mapped_coverage",
}

CLASS_CRITICAL_DISCLOSURE_FIELDS = {
    "dose_with_unit",
    "epa_or_dha_disclosed",
    "sports_active_dose",
    "total_cfu",
    "named_strain",
    "micronutrient_panel_dose_coverage",
}

SCORE_CAPPED_SOFT_DISCLOSURE_DEBT = {
    "botanical_anchor_only_evidence",
    "low_confidence_omega_breakdown",
    "total_cfu_not_disclosed",
    "sports_primary_dose_not_disclosed",
    "percent_dv_only_dose_evidence",
}

AUDIT_ONLY_SOFT_DISCLOSURE_TAGS = {
    "active_anchor_mass_evidence",
    "conservative_blend_anchor_mass",
    "enzyme_activity_dose_evidence",
    "omega_aggregate_epa_dha_evidence",
    "probiotic_product_cfu_evidence",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().upper()


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [part for part in value.split("|") if part]
    return []


def classify_row(row: Dict[str, Any]) -> str:
    """Return a stable release-readiness classification for one delta row."""
    v3_verdict = _norm(row.get("v3_verdict"))
    v3_safety = _norm(row.get("v3_safety_verdict") or v3_verdict)
    v4_verdict = _norm(row.get("v4_verdict"))
    v3_rank = SAFETY_RANK.get(v3_verdict)
    v4_rank = SAFETY_RANK.get(v4_verdict)
    v3_safety_rank = SAFETY_RANK.get(v3_safety)
    missing = set(_as_list(row.get("v4_completeness_missing")))
    soft_missing = set(_as_list(row.get("v4_completeness_soft_missing")))
    score_cap = _float(row.get("v4_completeness_score_cap"))
    verdict_ceiling = _norm(row.get("v4_completeness_verdict_ceiling"))

    if (
        v3_safety_rank is not None
        and v4_rank is not None
        and v3_safety_rank >= SAFETY_RANK["CAUTION"]
        and v4_rank < v3_safety_rank
    ):
        return "BLOCKER_SAFETY_DOWNGRADE"

    if v4_verdict == "NOT_SCORED":
        if missing and missing <= NO_USABLE_IDENTITY_FIELDS:
            return "OK_NOT_SCORED_NO_USABLE_IDENTITY"
        return "BLOCKER_UNEXPLAINED_NOT_SCORED"

    if missing & CLASS_CRITICAL_DISCLOSURE_FIELDS:
        return "BLOCKER_SCORED_WITH_HARD_COMPLETENESS_MISSING"

    if soft_missing & SCORE_CAPPED_SOFT_DISCLOSURE_DEBT:
        if score_cap is not None or verdict_ceiling in {"CAUTION", "POOR"}:
            return "OK_SCORED_WITH_SOFT_DISCLOSURE_CAP"
        return "BLOCKER_SOFT_DISCLOSURE_WITHOUT_CAP"

    if soft_missing & AUDIT_ONLY_SOFT_DISCLOSURE_TAGS:
        return "OK_SCORED_WITH_SOFT_AUDIT_TAG"

    if v3_verdict == "POOR" and v4_verdict == "SAFE":
        raw = _float(row.get("v4_raw_score"))
        if v3_safety == "SAFE" and raw is not None and raw >= 40.0:
            return "REVIEW_POOR_TO_SAFE_QUALITY_UPLIFT"
        return "BLOCKER_POOR_TO_SAFE_UNEXPLAINED"

    if v3_verdict == "SAFE" and v4_verdict == "POOR":
        return "REVIEW_SAFE_TO_POOR_QUALITY_TIGHTENING"

    if v3_verdict == "SAFE" and v4_verdict == "CAUTION":
        return "REVIEW_SAFE_TO_CAUTION_MORE_CONSERVATIVE"

    if v3_verdict == "POOR" and v4_verdict == "CAUTION":
        return "REVIEW_POOR_TO_CAUTION_MORE_CONSERVATIVE"

    return "OK_NO_RELEASE_CONCERN"


def build_audit_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    audited: List[Dict[str, Any]] = []
    for row in rows:
        if not row.get("in_shipped_universe"):
            continue
        item = dict(row)
        item["release_classification"] = classify_row(row)
        audited.append(item)
    return audited


def summarize(audited: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(row["release_classification"] for row in audited)
    blockers = {
        name: count
        for name, count in counts.items()
        if name.startswith("BLOCKER_") and count
    }
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "shipped_rows": len(audited),
        "classification_counts": dict(counts.most_common()),
        "blocker_counts": blockers,
        "blocker_total": sum(blockers.values()),
        "ready_for_v4_primary": sum(blockers.values()) == 0,
    }


def write_review_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    review_rows = [
        row for row in rows
        if row["release_classification"].startswith(("BLOCKER_", "REVIEW_"))
    ]
    cols = [
        "release_classification",
        "dsld_id",
        "brand_name",
        "product_name",
        "primary_class",
        "v4_module",
        "v3_verdict",
        "v3_safety_verdict",
        "v4_verdict",
        "v3_shipped_score",
        "v4_raw_score",
        "v4_score",
        "v4_completeness_missing",
        "v4_completeness_soft_missing",
        "v4_completeness_score_cap",
        "v4_completeness_verdict_ceiling",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in review_rows:
            out = {col: row.get(col) for col in cols}
            for key in ("v4_completeness_missing", "v4_completeness_soft_missing"):
                if isinstance(out[key], list):
                    out[key] = "|".join(out[key])
            writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=delta.DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--dist-db", type=Path, default=delta.DEFAULT_DIST_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    enriched_index = delta.canary.build_enriched_index(args.products_root)
    scored_index = delta.canary.build_scored_index(args.products_root)
    shipped_universe = delta.load_shipped_universe(args.dist_db)
    rows = delta.build_rows(enriched_index, scored_index)
    for row in rows:
        row["in_shipped_universe"] = (
            (not shipped_universe) or (row.get("dsld_id") in shipped_universe)
        )
    audited = build_audit_rows(rows)
    summary = summarize(audited)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_review_csv(audited, args.out_dir / "review_queue.csv")

    print(json.dumps(summary, indent=2))
    if summary["blocker_total"]:
        print(
            f"BLOCKER: {summary['blocker_total']} release-readiness blockers. "
            f"See {args.out_dir / 'review_queue.csv'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
