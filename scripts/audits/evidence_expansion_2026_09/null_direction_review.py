#!/usr/bin/env python3
"""GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW — measure, do not change (read-only).

The generic Evidence dimension multiplies a record's points by its effect
direction: positive_strong 1.0, positive_weak 0.85, mixed 0.6, null 0.25,
negative 0.0 (scripts/scoring_v4/modules/generic_evidence.py:85 and
scripts/scoring_v4/config/quality_score.json:200).

So a high-quality trial showing NO benefit earns Evidence credit, while an
ingredient with no record at all earns none. Curating null evidence — which this
project must do to stay honest — therefore RAISES some products' scores under the
current rule. This report quantifies the existing behaviour so the semantics can
be decided separately. It changes nothing and proposes no replacement.

    python3 scripts/audits/evidence_expansion_2026_09/null_direction_review.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_applicability import reviewed_entries  # noqa: E402
from scoring_v4.modules import generic_evidence as ge  # noqa: E402

WATCHED = ("null", "mixed", "negative")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()
    registry = reviewed_entries()
    by_direction = collections.defaultdict(list)
    for entry_id, entry in registry.items():
        by_direction[entry.get("effect_direction")].append(entry_id)

    products = collections.defaultdict(collections.Counter)
    only_direction = collections.Counter()
    record_products = collections.Counter()
    examples = collections.defaultdict(list)
    scored = 0
    for line in args.slim.open():
        product = json.loads(line)
        if product["module"] == "probiotic":
            continue
        matched = [m["id"] for m in product["accepted_matches"]]
        if not matched:
            continue
        scored += 1
        carrying = [i for i in matched if ge._entry_raw_points(registry.get(i, {})) > 0]
        for direction in WATCHED:
            hit = [i for i in matched if i in by_direction[direction]]
            if hit:
                products[direction][product["module"]] += 1
                for entry_id in hit:
                    record_products[entry_id] += 1
            if carrying and all(i in by_direction[direction] for i in carrying):
                only_direction[direction] += 1
                if len(examples[direction]) < 8:
                    examples[direction].append({
                        "dsld_id": product["dsld_id"], "brand": product["brand_name"],
                        "product_name": product["product_name"], "evidence": product["evidence"],
                        "records": carrying})

    lines = ["# GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW", "",
             "Measured on the corpus re-scored 2026-09-17. **Nothing here is implemented or proposed as a fix** — "
             "it exists so the Evidence-direction semantics can be decided as its own bounded scoring question, "
             "outside the evidence-expansion project.", "",
             "## The rule today", "",
             "| effect_direction | multiplier |", "|---|---:|"] + \
            [f"| {k} | {v} |" for k, v in ge.EFFECT_DIRECTION_MULTIPLIERS.items()] + \
            ["", "A record's points are `study_type base × evidence_level multiplier × direction multiplier × "
             "enrollment band`. `null` keeps 25% of the points and `mixed` 60%, so a rigorous no-benefit trial "
             "scores above an ingredient PharmaGuide has never reviewed (which scores 0).", "",
             "## Records with these directions today", ""]
    for direction in WATCHED:
        ids = sorted(by_direction[direction])
        lines += [f"### {direction} — {len(ids)} record(s)", "",
                  "| record | study_type | evidence_level | points a match earns | products matching it |",
                  "|---|---|---|---:|---:|"]
        for entry_id in ids:
            entry = registry[entry_id]
            lines.append(f"| `{entry_id}` | {entry.get('study_type')} | {entry.get('evidence_level')} | "
                         f"{ge._entry_raw_points(entry):.2f} | {record_products.get(entry_id, 0)} |")
        lines.append("")

    lines += ["## Product impact of the current rule", "",
              f"Of {scored} scored non-probiotic products with at least one accepted evidence match:", "",
              "| direction | products matching such a record | products whose ONLY point-carrying matches have "
              "this direction |", "|---|---:|---:|"]
    for direction in WATCHED:
        lines.append(f"| {direction} | {sum(products[direction].values())} | {only_direction[direction]} |")
    lines += ["", "The second column counts products whose only POINT-CARRYING matches have this direction. ",
              "**Correction (2026-09-18): that is not the same as the score resting on them.** The production "
              "projection in `null_direction_projection.json` scored all 2,446 affected products both ways and only "
              "**151** change at all. For most of the rest a floor already sets the dimension, so the null record's "
              "points are invisible.", "",
              "Worked example — 252794 Vitamin B12 1% (Cyanocobalamin), measured with the production scorer:", "",
              "| | clinical_evidence_pipeline | primary_evidence_floor | dimension score |", "|---|---:|---:|---:|",
              "| current (null = 0.25) | 1.35 | 10.0 (nutrition authority) | **10.0** |",
              "| candidate (null = 0) | 0.0 | 10.0 (nutrition authority) | **10.0** |", "",
              "The DRI-essential nutrition-authority floor sets this product's Evidence, not the null record. Any "
              "claim that these products are 'scored on evidence that did not show benefit' is wrong for the "
              "floor-carrying majority; it is true only for the 151 products listed as movers in the projection, "
              "where the dimension goes 1.5 -> 0.0.", ""]
    for direction in WATCHED:
        if examples[direction]:
            lines += [f"### Examples — Evidence carried only by `{direction}` records", "",
                      "| dsld_id | brand | product | Evidence /20 | records |", "|---|---|---|---:|---|"]
            for row in examples[direction]:
                lines.append(f"| {row['dsld_id']} | {row['brand']} | {row['product_name']} | {row['evidence']} | "
                             f"{', '.join(row['records'])} |")
            lines.append("")

    lines += ["## What this means for Wave 1", "",
              "Curating null and negative evidence accurately is required. Under the current rule some of that "
              "evidence would RAISE Evidence on approval. Phase 1 therefore: curates it, keeps it pending, flags "
              "every projected rise driven by a null-only record, and does not propose those records for approval "
              "until the semantics are decided.", "",
              "## Open question (for a separate decision, not this project)", "",
              "\"Research exists and is high quality\" and \"evidence supports this product working\" are different "
              "facts that the single direction multiplier currently merges. Any replacement needs its own "
              "projection and reviewer-benchmark check before it ships.", ""]
    (OUT / "GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md").write_text("\n".join(lines) + "\n")
    print(f"products with a null-record match: {sum(products['null'].values())}; "
          f"null-only point carriers: {only_direction['null']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
