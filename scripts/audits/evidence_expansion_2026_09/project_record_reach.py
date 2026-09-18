#!/usr/bin/env python3
"""How many products a proposed record would actually reach (read-only).

A proposed record's value is the number of products it would apply to, not the
number of papers behind it. This counts, per identity: products carrying that
canonical id, how many satisfy the proposed daily-dose floor, and how many of
those sit at Evidence 0 today.

Row fields are read the way the canonical dose profiler reads them
(``unit_normalized``, ``quantity``, ``form_id``) rather than re-guessed - two
earlier ad-hoc readers in this project used ``unit`` and silently produced zero.

    python3 scripts/audits/evidence_expansion_2026_09/project_record_reach.py \
        --slim <slim.jsonl> --proposals <proposals.json>

``proposals.json`` maps canonical_id -> minimum daily dose in mg, or null for a
record that deliberately carries no dose policy.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001, "gram(s)": 1000.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--proposals", required=True, type=Path)
    parser.add_argument("--out", default="wave2_projected_reach.json")
    args = parser.parse_args()
    floors = json.loads(args.proposals.read_text())

    products = collections.Counter()
    applies = collections.Counter()
    zero = collections.Counter()
    zero_applies = collections.Counter()
    below = collections.Counter()
    for line in args.slim.open():
        product = json.loads(line)
        best: dict[str, float | None] = {}
        for row in product["rows"]:
            canonical = row.get("canonical_id")
            if canonical not in floors:
                continue
            # An evidence record reaches a product only through a SCORABLE active
            # row. 126 of amla's 179 product rows are inactive_non_scorable, and
            # counting them would have overstated its reach by more than threefold.
            if row.get("role_classification") != "active_scorable":
                continue
            scale = MG.get(str(row.get("unit_normalized") or "").lower())
            value = row.get("quantity")
            mg = value * scale if scale and isinstance(value, (int, float)) and value > 0 else None
            if canonical not in best or (mg or 0) > (best[canonical] or 0):
                best[canonical] = mg
        at_zero = (product.get("evidence") or 0) == 0
        for canonical, mg in best.items():
            products[canonical] += 1
            if at_zero:
                zero[canonical] += 1
            floor = floors[canonical]
            if floor is None or (mg is not None and mg >= float(floor)):
                applies[canonical] += 1
                if at_zero:
                    zero_applies[canonical] += 1
            else:
                below[canonical] += 1

    payload = {"_metadata": {
        "note": "Read-only reach projection for proposed records. No record exists yet; nothing scored.",
        "dose_floor_semantics": "null means the record deliberately carries no dose policy, as INGR_CRANBERRY does."},
        "identities": {canonical: {
            "proposed_min_daily_dose_mg": floors[canonical],
            "products_carrying_the_identity": products[canonical],
            "products_the_record_would_apply_to": applies[canonical],
            "products_below_the_dose_floor_or_undosed": below[canonical],
            "products_at_evidence_zero_today": zero[canonical],
            "evidence_zero_products_the_record_would_reach": zero_applies[canonical],
        } for canonical in floors}}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(f"{'identity':22s} {'carrying':>9} {'would apply':>12} {'below floor':>12} {'ev0 now':>8} {'ev0 reached':>12}")
    for canonical in floors:
        print(f"{canonical:22s} {products[canonical]:9d} {applies[canonical]:12d} {below[canonical]:12d} "
              f"{zero[canonical]:8d} {zero_applies[canonical]:12d}")
    print(f"\ntotal Evidence=0 products the six proposed records would reach: "
          f"{sum(zero_applies.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
