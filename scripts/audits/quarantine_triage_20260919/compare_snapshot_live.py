#!/usr/bin/env python3
"""Generalized frozen-snapshot vs live-DSLD comparator — Phase-3 integration gate.

Team instructions #8 (stale source handling) and #13 (E2 unit-corruption cases):
for every reviewed product, establish whether the frozen ingest record still
matches live DSLD, and classify the change:

  unchanged_since_snapshot        — live identical on the compared fields
  changed_upstream                — live differs on a non-gating field
  upstream_change_requires_re_review — live differs on a row driving scoring,
                                      completeness or safety (needs a receipt)
  upstream_change_resolves_quarantine — the frozen defect is gone upstream
  fetch_failed                    — live record unavailable/not retrievable

The frozen record is never modified and never overwritten by live data: the
historical product ID keeps its historical label values.

Usage:
  compare_snapshot_live.py --ids 223563,223572,... \
      --raw-root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" \
      --out reports/quarantine_triage_2026_09_19/snapshot_vs_live.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LIVE_URL = "https://api.ods.od.nih.gov/dsld/v9/label/{dsld_id}"

# Rows whose movement changes a scoring/completeness/safety conclusion.
GATING_TOKENS = (
    "vitamin a",
    "vitamin d",
    "niacin",
    "magnesium",
    "folate",
    "calcium",
    "withaferin",
    "miroestrol",
    "ginkgolic",
    "edta",
    "silver",
    "citrus bioflavonoid",
)


def find_raw(pid: str, raw_roots: list) -> Path | None:
    for root in raw_roots:
        for candidate in sorted(root.glob(f"*/{pid}.json")):
            return candidate
    return None


def quantity_summary(row: dict) -> dict:
    quantities = row.get("quantity") or []
    out = []
    for q in quantities:
        if not isinstance(q, dict):
            continue
        groups = q.get("dailyValueTargetGroup") or [{}]
        out.append(
            {
                "per": f"{q.get('servingSizeQuantity')}{q.get('servingSizeUnit') or ''}",
                "amount": q.get("quantity"),
                "unit": q.get("unit"),
                "percent": (groups[0] or {}).get("percent") if groups else None,
                "dv_group": (groups[0] or {}).get("name") if groups else None,
            }
        )
    return {"quantities": out, "forms": [f.get("name") for f in (row.get("forms") or []) if isinstance(f, dict)]}


def flatten(rows: list, prefix: str = "") -> dict:
    """name -> quantity summary, walking nestedRows."""
    out = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        path = f"{prefix}{row.get('name')}"
        out[path] = quantity_summary(row)
        nested = row.get("nestedRows") or []
        if nested:
            out.update(flatten(nested, prefix=f"{path} > "))
    return out


def normalize(entries: dict) -> dict:
    """Order-independent, content-only comparison key."""
    return {
        name: sorted(
            (q.get("amount"), str(q.get("unit")), q.get("percent"), q.get("dv_group"))
            for q in value.get("quantities") or []
        )
        for name, value in entries.items()
    }


def fetch_live(dsld_id: str) -> tuple[dict | None, str | None]:
    url = LIVE_URL.format(dsld_id=dsld_id)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response), None
        except urllib.error.HTTPError as exc:
            return None, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 — recorded verbatim
            if attempt == 2:
                return None, f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return None, "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", required=True)
    parser.add_argument(
        "--raw-root",
        default=str(
            Path.home() / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands"
        ),
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    roots = [Path(p).expanduser() for p in args.raw_root.split(os.pathsep)]
    ids = [token.strip() for token in args.ids.split(",") if token.strip()]

    report = {}
    for pid in ids:
        entry: dict = {"dsld_id": pid}
        path = find_raw(pid, roots)
        if path is None:
            entry["classification"] = "snapshot_absent"
            report[pid] = entry
            continue
        frozen = json.loads(path.read_bytes())
        entry["snapshot_source"] = str(path)
        entry["snapshot_name"] = frozen.get("fullName")
        entry["snapshot_serving_sizes"] = frozen.get("servingSizes")
        live, error = fetch_live(pid)
        if live is None:
            entry["classification"] = "fetch_failed"
            entry["fetch_error"] = error
            report[pid] = entry
            continue
        entry["live_name"] = live.get("fullName")
        entry["live_serving_sizes"] = live.get("servingSizes")

        frozen_rows = flatten(frozen.get("ingredientRows") or [])
        live_rows = flatten(live.get("ingredientRows") or [])
        only_frozen = sorted(set(frozen_rows) - set(live_rows))
        only_live = sorted(set(live_rows) - set(frozen_rows))
        changed = []
        for name in sorted(set(frozen_rows) & set(live_rows)):
            if normalize({name: frozen_rows[name]}) != normalize({name: live_rows[name]}):
                changed.append(
                    {
                        "row": name,
                        "snapshot": frozen_rows[name],
                        "live": live_rows[name],
                    }
                )
        entry["rows_only_in_snapshot"] = only_frozen
        entry["rows_only_in_live"] = only_live
        entry["rows_changed"] = changed

        gating_changes = [
            item["row"]
            for item in changed
            if any(token in item["row"].lower() for token in GATING_TOKENS)
        ]
        gating_missing = [
            name
            for name in only_frozen
            if any(token in name.lower() for token in GATING_TOKENS)
        ]
        if not changed and not only_frozen and not only_live:
            entry["classification"] = "unchanged_since_snapshot"
        elif gating_changes or gating_missing or only_live:
            entry["classification"] = "upstream_change_requires_re_review"
            entry["gating_rows"] = sorted(set(gating_changes) | set(gating_missing))
        else:
            entry["classification"] = "changed_upstream"
        report[pid] = entry

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    summary: dict = {}
    for pid, entry in report.items():
        summary.setdefault(entry.get("classification"), []).append(pid)
    print(json.dumps(summary, indent=1))
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
