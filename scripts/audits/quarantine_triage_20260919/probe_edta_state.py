#!/usr/bin/env python3
"""Read-only probe: current pipeline state for the 16 standalone oral EDTA products.

Runs the real cleaner on each frozen raw DSLD record, then the v4 scorer, and
prints the safety verdict / quarantine reason / identity resolution so the
Phase-3 clinical-policy change can be scoped against measured behaviour.

Usage:
    "$PG_PYTHON" probe_edta_state.py [--ids a,b,c] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

CORPUS = Path(
    os.environ.get("PG_BRAND_CORPUS")
    or os.path.expanduser("~/Downloads/PharmaGuide_Datasets/staging/brands")
)

EDTA_IDS = [
    "252358", "252426", "253331", "253335", "253336", "253339", "253350",
    "253357", "311259", "311260", "311261", "311262", "312449", "312450",
    "312451", "312452",
]


def load_raw(dsld_id: str) -> dict | None:
    for path in CORPUS.glob(f"*/{dsld_id}.json"):
        return json.loads(path.read_text())
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default=",".join(EDTA_IDS))
    parser.add_argument("--out")
    args = parser.parse_args()

    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4

    normalizer = EnhancedDSLDNormalizer()
    rows = []
    for dsld_id in [t.strip() for t in args.ids.split(",") if t.strip()]:
        raw = load_raw(dsld_id)
        if raw is None:
            rows.append({"dsld_id": dsld_id, "error": "absent from corpus"})
            continue
        try:
            cleaned = normalizer.normalize_product(raw)
            scored = score_product_v4(cleaned)
        except Exception:
            rows.append(
                {
                    "dsld_id": dsld_id,
                    "product": raw.get("fullName"),
                    "error": traceback.format_exc(limit=3),
                }
            )
            continue
        breakdown = scored.get("v4_breakdown") or {}
        safety = breakdown.get("safety_gate") or {}
        actives = [
            {
                "name": row.get("name") or row.get("standardName"),
                "standard_name": row.get("standardName") or row.get("standard_name"),
                "canonical_id": row.get("canonical_id"),
                "quantity": row.get("quantity") or row.get("amount"),
                "unit": row.get("unit_normalized") or row.get("unit"),
                "role": row.get("role"),
            }
            for row in (cleaned.get("activeIngredients") or [])
            if isinstance(row, dict)
        ]
        rows.append(
            {
                "dsld_id": dsld_id,
                "product": raw.get("fullName"),
                "ingredient_group": [
                    r.get("ingredientGroup")
                    for r in (raw.get("ingredientRows") or [])
                    if isinstance(r, dict)
                ],
                "cleaned_actives": actives,
                "v4_verdict": scored.get("v4_verdict"),
                "score": scored.get("quality_score_v4_100"),
                "score_unavailable_reason": scored.get("score_unavailable_reason"),
                "blocking_reason": scored.get("blocking_reason"),
                "not_scorable_reason": scored.get("not_scorable_reason"),
                "scoring_status": scored.get("scoring_status"),
                "safety": {
                    "verdict": safety.get("verdict"),
                    "quarantine_required": safety.get("quarantine_required"),
                    "quarantine_reason": safety.get("quarantine_reason"),
                    "matched_substance": safety.get("matched_substance"),
                    "signals": safety.get("safety_signals"),
                    "review_records": [
                        {
                            "rule_id": rec.get("rule_id"),
                            "substance": rec.get("substance"),
                            "matched_role": rec.get("matched_role"),
                            "missing": rec.get("missing_requirements"),
                        }
                        for rec in (safety.get("review_records") or [])
                    ],
                },
            }
        )

    text = json.dumps(rows, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    for row in rows:
        print(
            f"{row['dsld_id']:>7} | {str(row.get('product'))[:38]:<38} | "
            f"verdict={row.get('v4_verdict')} | score={row.get('score')} | "
            f"unavail={row.get('score_unavailable_reason')} | "
            f"quar={(((row.get('safety') or {}).get('quarantine_reason')))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
