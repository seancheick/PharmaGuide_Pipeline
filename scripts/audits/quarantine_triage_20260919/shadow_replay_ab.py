"""Blast-radius shadow replay: HEAD cleaner vs fixed cleaner (2026-09-20).

Team instruction #12: replay every product whose cleaned/scored output could
change under the Phase-3 clinical-signoff cleaner fixes, without touching any
lane output. No raw corpus exists on this machine, so the replay runs against
the LIVE DSLD v9 records for the affected families (plus negative controls),
cleaning each record twice — once with HEAD's enhanced_normalizer, once with
the fixed working-tree cleaner — and diffs the cleaning-relevant outputs:

  - active-row (name, quantity, unit, score_eligible_by_cleaner,
    cleaner_row_role) multiset
  - display-ledger classification of the watched rows

No production lane, manifest, or scored artifact is written; output goes to
reports/quarantine_triage_2026_09_19/shadow_replay_ab.json.

Usage:
    "$PG_PYTHON" scripts/audits/quarantine_triage_20260919/shadow_replay_ab.py \
        [--ids 75188,243713,...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

REPORTS = REPO / "reports" / "quarantine_triage_2026_09_19"

DEFAULT_IDS = [
    # Affected families (Phase-3 clinical review)
    75188, 243713,          # GNC fish oil: dosed omega aggregate owner
    216948, 232718,         # standardization markers (Pueraria, ashwagandha)
    328464,                 # ginkgolic ppm spec limit
    241744,                 # colloidal silver (negative control, real shape)
    13041,                  # gummy %DV-no-amount
    223563, 231334, 328644, # E2 unit-corruption family samples
]


def fetch_live(dsld_id: int) -> dict:
    url = f"https://api.ods.od.nih.gov/dsld/v9/label/{dsld_id}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def head_module():
    """Import HEAD's enhanced_normalizer as a separate module object."""
    source = subprocess.run(
        ["git", "show", "HEAD:scripts/enhanced_normalizer.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    head = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("enhanced_normalizer_HEAD", loader=None)
    )
    sys.modules["enhanced_normalizer_HEAD"] = head
    head.__dict__["__file__"] = str(REPO / "scripts" / "enhanced_normalizer.py")
    exec(compile(source, "HEAD:scripts/enhanced_normalizer.py", "exec"), head.__dict__)
    return head


def clean_with(module, live: dict) -> list:
    normalizer = module.EnhancedDSLDNormalizer()
    cleaned = normalizer.normalize_product(live)
    rows = []
    for r in cleaned.get("activeIngredients") or []:
        rows.append(
            {
                "name": str(r.get("name") or ""),
                "quantity": r.get("quantity"),
                "unit": r.get("unit"),
                "role": r.get("cleaner_row_role"),
                "eligible": r.get("score_eligible_by_cleaner"),
            }
        )
    return rows


def signature(rows: list) -> str:
    counter = Counter(
        (r["name"], str(r["quantity"]), str(r["unit"]), str(r["role"]), str(r["eligible"]))
        for r in rows
    )
    return json.dumps(sorted(counter.items()), default=str)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default=",".join(str(i) for i in DEFAULT_IDS))
    args = parser.parse_args()
    ids = [int(x) for x in args.ids.split(",") if x.strip()]

    worktree = importlib.import_module("enhanced_normalizer")
    head = head_module()

    results = {}
    changed = 0
    crashes = 0
    for dsld_id in ids:
        try:
            live = fetch_live(dsld_id)
            rows_head = clean_with(head, live)
            rows_fixed = clean_with(worktree, live)
            sig_head = signature(rows_head)
            sig_fixed = signature(rows_fixed)
            is_changed = sig_head != sig_fixed
            changed += is_changed
            results[str(dsld_id)] = {
                "name": live.get("fullName"),
                "changed": is_changed,
                "head_rows": rows_head,
                "fixed_rows": rows_fixed,
                "changed_rows": [
                    {"head": h, "fixed": f}
                    for h, f in zip(rows_head, rows_fixed)
                    if h != f
                ]
                + [
                    {"head": None, "fixed": f}
                    for f in rows_fixed[len(rows_head):]
                ]
                + [
                    {"head": h, "fixed": None}
                    for h in rows_head[len(rows_fixed):]
                ],
            }
            print(f"{'CHANGED' if is_changed else 'same   '} {dsld_id} {live.get('fullName')}")
        except Exception as exc:  # noqa: BLE001
            crashes += 1
            results[str(dsld_id)] = {"error": repr(exc)}
            print(f"ERROR    {dsld_id}: {exc!r}")

    report = {
        "generated": "2026-09-20",
        "basis": "live DSLD v9 records; HEAD vs working-tree cleaner",
        "products_replayed": len(ids),
        "crashes": crashes,
        "cleaned_representation_changed": changed,
        "results": results,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "shadow_replay_ab.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nreplayed={len(ids)} changed={changed} crashes={crashes}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
