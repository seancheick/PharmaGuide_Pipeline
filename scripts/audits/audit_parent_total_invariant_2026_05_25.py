#!/usr/bin/env python3
"""Audit: enricher parent_total invariant for canonical_id-paired ingredients.

For every product in the enriched corpus, finds canonical_id groups in
ingredients_scorable that contain BOTH:
  - a top-level row (is_nested_ingredient=False), AND
  - at least one nested child (is_nested_ingredient=True) with a usable dose.

For each such group, the enricher's _mark_parent_total_rows
(enrich_supplements_v3.py:5647) SHOULD mark the top-level row
is_parent_total=True so the scorer skips it in Section A and only
the form-specific child contributes its bio_score.

Outputs:
  - JSON report at scripts/audits/parent_total_invariant_report.json
    containing pass + miss groups with full context for triage.
  - stdout summary with PASS / MISS counts.

Misses are NOT auto-classified as bugs. Investigation 2026-05-25
identified two miss categories that require human triage:

  TRUE BUG (label-restatement):
    e.g. CVS 271087 — Vitamin C 500 mg top-level + Vitamin C 500 mg
    nested under "Polyphenol-C Proprietary Blend". Same dose appearing
    twice; both score-eligible; scorer counts both → double-count.

  NOT A BUG (multi-source coincidence):
    e.g. CVS 82369 — top-level Caffeine 50 mg + nested Caffeine 15 mg
    under "Green Tea Extract". Two genuinely different sources of
    caffeine. Both should remain scorable.

Use the JSON report to classify each miss, then extend
_mark_parent_total_rows with a narrow rule for the true-bug cases.

Usage:
    python3 scripts/audits/audit_parent_total_invariant_2026_05_25.py
    python3 scripts/audits/audit_parent_total_invariant_2026_05_25.py --json-only
    python3 scripts/audits/audit_parent_total_invariant_2026_05_25.py --output /tmp/foo.json
"""

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
USABLE_DOSE_UNITS = {"mg", "mcg", "ug", "µg", "g", "iu", "cfu", "billion cfu", "ml"}


def has_usable_dose(row):
    q = row.get("quantity") or 0
    try:
        q = float(q)
    except (TypeError, ValueError):
        return False
    if q <= 0:
        return False
    unit = (row.get("unit_normalized") or row.get("unit") or "").strip().lower()
    return unit in USABLE_DOSE_UNITS


def scan_product(prod):
    """Return (pass_groups, miss_groups) for one enriched product."""
    iqd = prod.get("ingredient_quality_data") or {}
    scor = iqd.get("ingredients_scorable") or []
    groups = {}
    for r in scor:
        cid = r.get("canonical_id")
        if cid:
            groups.setdefault(cid, []).append(r)

    passes, misses = [], []
    for cid, group in groups.items():
        if len(group) < 2:
            continue
        top = [r for r in group if not r.get("is_nested_ingredient")]
        nested_with_dose = [r for r in group if r.get("is_nested_ingredient") and has_usable_dose(r)]
        if not top or not nested_with_dose:
            continue
        any_top_marked = any(r.get("is_parent_total") for r in top)
        record = {
            "dsld_id": prod.get("dsld_id") or prod.get("id"),
            "product_name": prod.get("product_name") or prod.get("fullName"),
            "brand": prod.get("brand_name") or prod.get("brandName"),
            "canonical_id": cid,
            "top_level_rows": [
                {
                    "name": r.get("name"),
                    "quantity": r.get("quantity"),
                    "unit": r.get("unit"),
                    "matched_form": r.get("matched_form"),
                    "bio_score": r.get("bio_score"),
                    "is_parent_total": r.get("is_parent_total"),
                }
                for r in top
            ],
            "nested_children_with_dose": [
                {
                    "name": r.get("name"),
                    "parent_blend": r.get("parent_blend"),
                    "quantity": r.get("quantity"),
                    "unit": r.get("unit"),
                    "matched_form": r.get("matched_form"),
                    "bio_score": r.get("bio_score"),
                }
                for r in nested_with_dose
            ],
        }
        if any_top_marked:
            passes.append(record)
        else:
            misses.append(record)
    return passes, misses


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--json-only", action="store_true", help="suppress stdout summary")
    ap.add_argument(
        "--output",
        default=str(REPO_ROOT / "scripts/audits/parent_total_invariant_report.json"),
        help="path for the JSON report",
    )
    args = ap.parse_args()

    all_passes, all_misses = [], []
    paths = sorted(
        glob.glob(str(REPO_ROOT / "scripts/products/output_*_enriched/enriched/*.json"))
    )
    for p in paths:
        try:
            with open(p) as f:
                data = json.load(f)
        except Exception as e:
            print(f"SKIP {p}: {e}", file=sys.stderr)
            continue
        prods = data.get("products", data) if isinstance(data, dict) else data
        if not isinstance(prods, list):
            continue
        for prod in prods:
            passes, misses = scan_product(prod)
            all_passes.extend(passes)
            all_misses.extend(misses)

    miss_by_cid = Counter(m["canonical_id"] for m in all_misses)
    pass_by_cid = Counter(p_["canonical_id"] for p_ in all_passes)

    report = {
        "scanned_enriched_files": len(paths),
        "pass_group_count": len(all_passes),
        "miss_group_count": len(all_misses),
        "pass_groups_by_canonical_id": dict(pass_by_cid.most_common()),
        "miss_groups_by_canonical_id": dict(miss_by_cid.most_common()),
        "passes": all_passes,
        "misses": all_misses,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    if not args.json_only:
        print(f"Scanned {len(paths)} enriched batch files")
        print(f"PASS groups (parent_total correctly marked): {len(all_passes)}")
        print(f"MISS groups (parent_total NOT marked; needs triage): {len(all_misses)}")
        print(f"\nMisses by canonical_id (top 20):")
        for cid, n in miss_by_cid.most_common(20):
            print(f"  {cid:35s} {n}")
        print(f"\nFull report written to: {out_path}")
        print(
            "\nTriage guidance: each miss is either a label-restatement bug "
            "(e.g. CVS 271087 Vitamin C 500mg x2) or a multi-source coincidence "
            "(e.g. CVS 82369 Caffeine + Green Tea). See audit script header."
        )


if __name__ == "__main__":
    main()
