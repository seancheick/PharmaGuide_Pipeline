#!/usr/bin/env python3
"""Final source-resolution phase: fetch live DSLD + dump the rows under review.

Read-only. Never modifies the frozen corpus and never writes into a product lane.
For each requested DSLD id it:

  1. fetches ``GET https://api.ods.od.nih.gov/dsld/v9/label/{id}`` and saves the
     raw JSON plus retrieval metadata under ``source_resolution_20260920/live/``;
  2. locates the frozen ingest record in the staging corpus and compares the
     fields that matter to each open item (ingredient rows / quantities / units /
     forms / serving sizes);
  3. prints a human-readable block: the live row tree flattened with per-serving
     quantities and any form/source notes, the frozen row tree, and the
     ``pdf``/``thumbnail``/``netContents`` provenance needed to consult the
     *printed* label.

Usage:
  fetch_live_source_20260920.py --ids 269360,228823 --out <dir>
  fetch_live_source_20260920.py --ids all            # the whole Phase-3 set
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LIVE_URL = "https://api.ods.od.nih.gov/dsld/v9/label/{dsld_id}"
HERE = Path(__file__).resolve().parent
DEFAULT_RAW_ROOTS = [
    Path(os.environ.get("PG_RAW_ROOT", "")) / ""
    if os.environ.get("PG_RAW_ROOT")
    else None,
    Path.home() / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands",
]
DEFAULT_RAW_ROOTS = [p for p in DEFAULT_RAW_ROOTS if p]

# The complete Phase-3 source-resolution set, by open item.
TARGETS: dict[str, list[str]] = {
    "A_e2_unit_defects": ["223563", "223572", "231334", "231335", "263865", "328644"],
    "B_needs_info": ["12300", "254396", "254413", "75291"],
    "C_vitamin_a_form_gap": ["228823", "243799", "243808", "243812", "243815"],
    "D_folate_residuals": ["201420", "246430", "243808"],
    "E_serrapeptase": ["269360"],
}


def all_ids() -> list[str]:
    seen: list[str] = []
    for ids in TARGETS.values():
        for i in ids:
            if i not in seen:
                seen.append(i)
    return seen


def find_raw(pid: str, roots: list[Path]) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        for candidate in sorted(root.glob(f"*/{pid}.json")):
            return candidate
    return None


def fetch_live(pid: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        LIVE_URL.format(dsld_id=pid),
        headers={"User-Agent": "PharmaGuide-source-resolution/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fmt_quantities(row: dict) -> str:
    out = []
    for q in row.get("quantity") or []:
        if not isinstance(q, dict):
            continue
        out.append(
            "{q} {u} per {s}{su}{extra}".format(
                q=q.get("quantity"),
                u=q.get("unit") or "",
                s=q.get("servingSizeQuantity") or "",
                su=q.get("servingSizeUnit") or "",
                extra=(
                    ", ".join(
                        f"from {k}={v}"
                        for k, v in (q.get("from") or {}).items()
                        if v
                    )
                    if isinstance(q.get("from"), dict)
                    else ""
                ),
            ).strip()
        )
    return " | ".join(out)


def live_rows(rows: list, depth: int = 0, out: list | None = None) -> list[str]:
    """Flatten the live ingredient tree with quantity/form provenance."""
    if out is None:
        out = []
    for row in rows or []:
        parts = [
            str(row.get("name") or row.get("originalIngredient") or "?").strip(),
            fmt_quantities(row),
            f"unii={row.get('uniiCode')}" if row.get("uniiCode") else "",
            f"form={row.get('forms')}" if row.get("forms") else "",
            f"notes={row.get('notes')}" if row.get("notes") else "",
            f"dv={row.get('percentDv')}" if row.get("percentDv") is not None else "",
            f"cat={row.get('category')}" if row.get("category") else "",
            f"dup={row.get('duplicate')}" if row.get("duplicate") is not None else "",
        ]
        out.append(("    " * depth) + " | ".join(p for p in parts if p))
        live_rows(row.get("nestedRows") or [], depth + 1, out)
    return out


def frozen_rows(rows: list, depth: int = 0, out: list | None = None) -> list[str]:
    if out is None:
        out = []
    for row in rows or []:
        parts = [
            str(row.get("name") or row.get("originalIngredient") or "?").strip(),
            (row.get("unit") or "").strip(),
            ", ".join(
                f"{k}={v}"
                for k, v in (
                    ("forms", row.get("forms")),
                    ("cat", row.get("category")),
                    ("blend", row.get("parentBlendMass")),
                    ("dv", row.get("dv") or row.get("dailyValue")),
                    ("inner", row.get("innerQuantity")),
                    ("off", row.get("offsetQuantity")),
                )
                if v not in (None, "", [], {})
            ),
        ]
        qty = row.get("quantity")
        if qty is None and "innerQuantity" in row:
            qty = row.get("innerQuantity")
            parts[1] = (row.get("innerUnit") or parts[1] or "").strip()
            parts.append("(inner)")
        out.append(("    " * depth) + f"{parts[0]} = {qty} {parts[1]}  [{parts[2]}]")
        frozen_rows(row.get("nestedRows") or row.get("nested") or [], depth + 1, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="all", help="comma list, or 'all'")
    ap.add_argument(
        "--out",
        default=str(HERE / "source_resolution_20260920" / "live"),
        help="dir for raw live JSON",
    )
    ap.add_argument("--raw-root", action="append", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ids = all_ids() if args.ids.strip() == "all" else [
        s.strip() for s in args.ids.split(",") if s.strip()
    ]
    roots = [Path(p) for p in (args.raw_root or [])] or DEFAULT_RAW_ROOTS
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    index: dict[str, dict] = {}
    for pid in ids:
        entry: dict = {"dsld_id": pid, "retrieved_at_utc": fetched_at}
        try:
            live = fetch_live(pid)
            entry["fetch"] = "ok"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:  # noqa: BLE001
            entry["fetch"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            index[pid] = entry
            print(f"!!! {pid}: FETCH FAILED — {entry['error']}")
            continue

        (outdir / f"{pid}.json").write_text(json.dumps(live, indent=1), encoding="utf-8")
        entry.update(
            {
                "fullName": live.get("fullName"),
                "brandName": live.get("brandName"),
                "src": live.get("src"),
                "entryDate": live.get("entryDate"),
                "offMarket": live.get("offMarket"),
                "productVersionCode": live.get("productVersionCode"),
                "pdf": live.get("pdf"),
                "thumbnail": live.get("thumbnail"),
                "netContents": live.get("netContents"),
                "servingSizes": live.get("servingSizes"),
                "servingsPerContainer": live.get("servingsPerContainer"),
                "saved_to": str(outdir / f"{pid}.json"),
            }
        )

        raw_path = find_raw(pid, roots)
        entry["frozen_record"] = str(raw_path) if raw_path else None
        frozen = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path else None

        if not args.quiet:
            print("=" * 78)
            print(f"{pid}  {live.get('brandName','')} — {live.get('fullName','')}")
            print(f"  live src={live.get('src')} entryDate={live.get('entryDate')} "
                  f"offMarket={live.get('offMarket')} version={live.get('productVersionCode')}")
            print(f"  servingSizes={json.dumps(live.get('servingSizes'))}")
            print(f"  netContents={json.dumps(live.get('netContents'))}")
            print(f"  pdf={live.get('pdf')}  thumbnail={bool(live.get('thumbnail'))}")
            print("  --- LIVE ingredientRows ---")
            for line in live_rows(live.get("ingredientRows") or []):
                print("   ", line)
            if live.get("otheringredients"):
                print("  --- LIVE otheringredients ---")
                print("    ", json.dumps(live["otheringredients"])[:600])
            if frozen:
                print("  --- FROZEN activeIngredients ---")
                for line in frozen_rows(
                    frozen.get("activeIngredients") or frozen.get("ingredientRows") or []
                ):
                    print("   ", line)
                print(f"  frozen servingSize={json.dumps(frozen.get('servingSizes'))} "
                      f"netContents={json.dumps(frozen.get('netContents'))}")
        index[pid] = entry

    idx_path = outdir.parent / "live_source_index_20260920.json"
    idx_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"\nfetched {sum(1 for v in index.values() if v.get('fetch') == 'ok')}/{len(ids)}"
          f"  index -> {idx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
