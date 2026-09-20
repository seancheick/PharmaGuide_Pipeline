#!/usr/bin/env python3
"""Cross-check E2 unit rows against DSLD sibling label versions (2026-09-20).

DSLD keeps several label records for one product (package-size and formula
revisions) and links them through ``labelRelationships``. They are independent
transcriptions of the *same printed panel*, so when a unit looks wrong on one
record the siblings are decisive evidence about the printed glyph — in-DSLD,
with no OCR involved.

For each E2 product this fetches every sibling record, extracts the vitamin A /
D / E rows, and reports the unit distribution plus the DS LD ids that agree and
disagree with the record under review.

Usage:
  compare_label_siblings_20260920.py --ids 223563,231334 --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE_DIR = HERE / "source_resolution_20260920" / "live"
API = "https://api.ods.od.nih.gov/dsld/v9/label/{id}"

E2_IDS = ["223563", "223572", "231334", "231335", "263865", "328644"]
FIELDS = ("vitamin a", "vitamin d3", "vitamin d", "vitamin e")

_cache: dict[str, dict] = {}


def fetch(pid: str) -> dict | None:
    if pid in _cache:
        return _cache[pid]
    try:
        req = urllib.request.Request(API.format(id=pid), headers={"User-Agent": "PG/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError):
        d = None
    _cache[pid] = d
    return d


def rows_of(d: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}

    def walk(rs, depth=0):
        for r in rs or []:
            nm = str(r.get("name") or r.get("originalIngredient") or "").strip().lower()
            if nm in FIELDS:
                for q in r.get("quantity") or []:
                    out.setdefault(nm, []).append({
                        "quantity": q.get("quantity"), "unit": q.get("unit"),
                        "per": f"{q.get('servingSizeQuantity')}{q.get('servingSizeUnit')}",
                        "depth": depth,
                        "forms": [f.get("name") for f in (r.get("forms") or [])],
                    })
            walk(r.get("nestedRows") or [], depth + 1)
    walk(d.get("ingredientRows") or [])
    return out


def index_sibling(payload: dict, pid: str) -> dict[str, int]:
    """Fold a sibling record into a ``(field, qty, unit)`` -> count index."""
    idx: dict[str, int] = {}
    live = payload.get(pid) or payload.get("live", {}).get(pid)
    rel = (live or {}).get("labelRelationships") or []
    for entry in rel:
        sib = str(entry.get("labelId"))
        d = fetch(sib)
        if not d:
            continue
        for field, rows in rows_of(d).items():
            for r in rows:
                key = f"{field}|{r['quantity']}|{r['unit']}"
                idx[key] = idx.get(key, 0) + 1
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=",".join(E2_IDS))
    ap.add_argument("--out", default=str(HERE / "source_resolution_20260920" /
                                         "e2_sibling_crosscheck_20260920.json"))
    args = ap.parse_args()
    ids = [s.strip() for s in args.ids.split(",") if s.strip()]

    result: dict[str, dict] = {}
    for pid in ids:
        live_path = LIVE_DIR / f"{pid}.json"
        if live_path.exists():
            live = json.loads(live_path.read_text())
        else:
            live = fetch(pid)
        own = rows_of(live or {})
        rel = (live or {}).get("labelRelationships") or []
        sibs = [str(e.get("labelId")) for e in rel]
        idx = index_sibling({pid: live}, pid)
        entry = {
            "dsld_id": pid,
            "brand": (live or {}).get("brandName"),
            "fullName": (live or {}).get("fullName"),
            "own_rows": own,
            "sibling_count": len(sibs),
            "siblings": sibs,
            "sibling_unit_index": idx,
            "retrieved_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        result[pid] = entry
        print("=" * 84)
        print(f"{pid}  {(live or {}).get('brandName')} — {(live or {}).get('fullName')}"
              f"   siblings={len(sibs)}")
        for f, rows in own.items():
            print(f"  own   {f}: {[(r['quantity'], r['unit']) for r in rows]}")
        for k in sorted(idx):
            print(f"  sibs  {k}: x{idx[k]}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
