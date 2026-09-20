#!/usr/bin/env python3
"""Dump the exact frozen-corpus source rows for the Phase-3 source-correction targets.

Read-only. Prints, per target DSLD id, the product-level statements (the catalog
disposition inputs) and the full nested active-ingredient tree with every
quantity variant / unit / category / forms value, so an RC-5 correction can be
keyed on the real ``raw_ingredient_text`` instead of a reconstruction from
memory.

Usage:
    "$PG_PYTHON" dump_frozen_targets.py [--ids 223563,223572,...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CORPUS = Path(
    os.environ.get("PG_BRAND_CORPUS")
    or os.path.expanduser("~/Downloads/PharmaGuide_Datasets/staging/brands")
)

DEFAULT_IDS = [
    # A — E2 unit defects
    "223563", "223572", "328644", "231334", "231335", "263865",
    # B — needs_info
    "12300", "254396", "254413", "75291",
    # C — Vitamin-A form gap (Bulk 1340)
    "228823", "243799", "243808", "243812", "243815",
    # D — folate residuals
    "201420", "246430",
    # E — serrapeptase
    "269360",
]


def find_record(dsld_id: str) -> Path | None:
    for path in CORPUS.glob(f"*/{dsld_id}.json"):
        return path
    return None


def _quantity_display(row: dict) -> list[str]:
    out = []
    q = row.get("quantity")
    if isinstance(q, list):
        for entry in q:
            if isinstance(entry, dict):
                out.append(f"{entry.get('quantity')} {entry.get('unit')!r}")
            else:
                out.append(repr(entry))
    elif isinstance(q, dict):
        out.append(f"{q.get('quantity')} {q.get('unit')!r}")
    else:
        out.append(f"{q} {row.get('unit')!r}")
    return out


def _walk(rows, depth=0):
    pad = "  " * depth
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        qtys = ", ".join(_quantity_display(row))
        print(
            f"{pad}- name={row.get('name')!r} cat={row.get('category')!r} "
            f"grp={row.get('ingredientGroup')!r} qty=[{qtys}] "
            f"dv={row.get('dailyValue')!r} unii={row.get('uniiCode')!r}"
        )
        forms = row.get("forms")
        if forms:
            for form in forms:
                if isinstance(form, dict):
                    print(
                        f"{pad}    form: name={form.get('name')!r} "
                        f"cat={form.get('category')!r} grp={form.get('ingredientGroup')!r} "
                        f"prefix={form.get('prefix')!r} unii={form.get('uniiCode')!r}"
                    )
        nested = row.get("ingredients") or row.get("nestedIngredients")
        if nested:
            _walk(nested, depth + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=",".join(DEFAULT_IDS))
    args = ap.parse_args()
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]

    print(f"corpus: {CORPUS}")
    for dsld_id in ids:
        path = find_record(dsld_id)
        print("\n" + "=" * 100)
        if path is None:
            print(f"!! {dsld_id}: NOT FOUND in corpus")
            continue
        rec = json.loads(path.read_text())
        print(f"DSLD {dsld_id}  ({path.relative_to(CORPUS)})")
        print(
            f"  brand={rec.get('brandName')!r} fullName={rec.get('fullName')!r} "
            f"status={rec.get('status')!r} offMarket={rec.get('offMarket')!r}"
        )
        print("  --- statements ---")
        for statement in rec.get("statements") or []:
            if isinstance(statement, dict):
                print(f"    type={statement.get('type')!r} notes={statement.get('notes')!r}")
        print("  --- ingredientRows ---")
        _walk(rec.get("ingredientRows"))
        other = rec.get("otherIngredients")
        if other:
            names = [
                i.get("name") for i in (other.get("ingredients") or [])
                if isinstance(i, dict)
            ][:40]
            print(f"  --- otherIngredients ({len(names)} shown) --- {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
