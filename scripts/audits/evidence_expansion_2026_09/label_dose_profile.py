#!/usr/bin/env python3
"""Measured label-dose distribution per identity (read-only).

What a label actually delivers decides whether a trial exposure is applicable,
so the packet carries measured amounts rather than an author's impression.

    python3 scripts/audits/evidence_expansion_2026_09/label_dose_profile.py --slim <slim.jsonl> ID [ID ...]
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("canonical_ids", nargs="+")
    args = parser.parse_args()
    wanted = set(args.canonical_ids)
    amounts: dict[str, list[float]] = collections.defaultdict(list)
    units: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    forms: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for line in args.slim.open():
        product = json.loads(line)
        for row in product["rows"]:
            canonical = row.get("canonical_id")
            if canonical not in wanted:
                continue
            units[canonical][row.get("unit_normalized")] += 1
            forms[canonical][row.get("form_id") or "(none)"] += 1
            scale = MG.get(str(row.get("unit_normalized") or "").lower())
            value = row.get("quantity")
            if scale and isinstance(value, (int, float)) and value > 0:
                amounts[canonical].append(value * scale)
    out = {}
    for canonical in args.canonical_ids:
        values = sorted(amounts[canonical])
        out[canonical] = {
            "dosed_rows": len(values),
            "unit_counts": dict(units[canonical].most_common()),
            "top_forms": dict(forms[canonical].most_common(5)),
            "mg_min": values[0] if values else None,
            "mg_p25": statistics.quantiles(values, n=4)[0] if len(values) > 3 else None,
            "mg_median": statistics.median(values) if values else None,
            "mg_p75": statistics.quantiles(values, n=4)[2] if len(values) > 3 else None,
            "mg_max": values[-1] if values else None,
        }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
