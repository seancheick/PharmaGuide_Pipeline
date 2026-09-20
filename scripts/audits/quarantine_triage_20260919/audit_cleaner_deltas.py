#!/usr/bin/env python3
"""Invariant audit of the cleaner A/B diff — Phase-3 integration gate.

Loads two arm JSONLs (:mod:`full_corpus_replay` signatures) plus the cleaner
diff, and checks the release-blocking invariants the team named:

  * no fabricated dose (a dose may not appear where the source had none)
  * no quantity transferred between ingredients
  * no silently lost source row
  * no lost scored dose owner
  * no lost safety-relevant row
  * no unexpected cross-family change

Usage:
  audit_cleaner_deltas.py --base BASE.jsonl --integrated INT.jsonl \
      --diff DIFF.json --safety-dir scripts/data --out audit.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> dict:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            record = json.loads(line)
            out[str(record.get("id"))] = record
    return out


def safety_index(data_dir: Path) -> dict:
    """Lowercased name/alias -> safety registry entry, for lost-signal checks."""
    index: dict = {}

    def register(name: str, entry: dict) -> None:
        key = str(name or "").strip().lower()
        if key:
            index.setdefault(key, entry)

    banned_path = data_dir / "banned_recalled_ingredients.json"
    if banned_path.exists():
        data = json.loads(banned_path.read_text(encoding="utf-8"))
        entries = data.get("ingredients") or data.get("banned_recalled") or data
        if isinstance(entries, dict):
            entries = list(entries.values())
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            status = entry.get("status") or entry.get("classification") or "banned"
            info = {
                "source": "banned_recalled_ingredients",
                "identity_id": entry.get("identity_id") or entry.get("id"),
                "status": status,
            }
            register(entry.get("standard_name"), info)
            register(entry.get("name"), info)
            for alias in entry.get("aliases") or []:
                register(alias, info)

    additives_path = data_dir / "harmful_additives.json"
    if additives_path.exists():
        data = json.loads(additives_path.read_text(encoding="utf-8"))
        entries = data.get("harmful_additives") or []
        if isinstance(entries, dict):
            entries = list(entries.values())
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            info = {
                "source": "harmful_additives",
                "identity_id": entry.get("identity_id") or entry.get("id"),
                "status": entry.get("status") or entry.get("severity"),
            }
            register(entry.get("standard_name"), info)
            register(entry.get("name"), info)
            for alias in entry.get("aliases") or []:
                register(alias, info)
    return index


def dosed(rows: list) -> dict:
    """Rows that are eligible AND carry a real quantity/unit."""
    out = {}
    for row in rows or []:
        quantity = row.get("q")
        unit = str(row.get("u") or "").strip().lower()
        if not row.get("elig"):
            continue
        if isinstance(quantity, (int, float)) and quantity > 0 and unit not in {
            "",
            "unspecified",
            "none",
            "n/a",
        }:
            out[f"{row.get('cid')}|{row.get('name')}|{row.get('path')}"] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--integrated", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--safety-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base = load_jsonl(Path(args.base))
    integrated = load_jsonl(Path(args.integrated))
    diff = json.loads(Path(args.diff).read_text(encoding="utf-8"))
    safety = safety_index(Path(args.safety_dir))

    findings: dict = {
        "fabricated_doses": [],
        "quantity_transfers": [],
        "lost_source_rows": [],
        "lost_dose_owners": [],
        "lost_safety_rows": [],
        "de_eligibilised_without_provenance": [],
        "ledger_provenance_violations": [],
        "rows_removed_from_actives_but_present_in_ledger": 0,
        "rows_removed_from_actives_and_absent_from_ledger": 0,
        "eligibility_count_changes": [],
        "outside_expected_families": [],
        "row_ops": Counter(),
        "family_product_counts": Counter(),
    }

    for item in diff["changed"]:
        dsld_id = str(item["id"])
        if item.get("crash_before") or item.get("crash_after"):
            continue
        left, right = base[dsld_id], integrated[dsld_id]
        reasons = item.get("reasons") or []
        for reason in reasons:
            findings["family_product_counts"][reason] += 1
        if "outside_expected_families" in reasons:
            findings["outside_expected_families"].append(
                {
                    "id": dsld_id,
                    "name": item.get("name"),
                    "brand": item.get("brand"),
                    "counts_before": item.get("counts_before"),
                    "counts_after": item.get("counts_after"),
                    "roles_before": item.get("roles_before"),
                    "roles_after": item.get("roles_after"),
                    "row_changes": item.get("row_changes"),
                }
            )

        before_dosed = dosed(left.get("actives"))
        after_dosed = dosed(right.get("actives"))
        before_elig = {
            f"{r.get('cid')}|{r.get('name')}|{r.get('path')}"
            for r in left.get("actives") or []
            if r.get("elig")
        }
        after_elig = {
            f"{r.get('cid')}|{r.get('name')}|{r.get('path')}"
            for r in right.get("actives") or []
            if r.get("elig")
        }

        # 1. Fabricated dose: a row that gained a positive quantity it never had.
        for change in item["row_changes"]:
            findings["row_ops"][change["op"]] += 1
            if change["op"] != "changed":
                continue
            delta = change.get("delta") or {}
            if "q" in delta:
                before_q, after_q = delta["q"].get("before"), delta["q"].get("after")
                had = isinstance(before_q, (int, float)) and before_q > 0
                has = isinstance(after_q, (int, float)) and after_q > 0
                if has and not had:
                    findings["fabricated_doses"].append(
                        {"id": dsld_id, "row": change["after"], "delta": delta}
                    )
                if had and has and before_q != after_q:
                    findings["quantity_transfers"].append(
                        {"id": dsld_id, "row": change["after"], "delta": delta}
                    )
                if had and not has:
                    findings["lost_dose_owners"].append(
                        {"id": dsld_id, "row": change["before"], "delta": delta}
                    )

        # 2. Rows removed while holding a scored dose.
        for change in item["row_changes"]:
            if change["op"] != "removed":
                continue
            row = change.get("before") or {}
            if row.get("elig") and isinstance(row.get("q"), (int, float)) and row["q"] > 0:
                findings["lost_dose_owners"].append({"id": dsld_id, "row": row})

        # 3. Source rows disappearing at the record level.
        before_counts = item.get("counts_before") or {}
        after_counts = item.get("counts_after") or {}
        if (before_counts.get("source_rows") or 0) > (after_counts.get("source_rows") or 0):
            findings["lost_source_rows"].append(
                {"id": dsld_id, "before": before_counts, "after": after_counts}
            )

        # 3b. Precise loss check: every source path that held an active row
        # before must still be enumerated by the after arm's label ledger.
        after_paths = set(right.get("source_paths") or [])
        before_paths = set(left.get("source_paths") or [])
        for path in sorted(before_paths - after_paths):
            findings["ledger_provenance_violations"].append(
                {"id": dsld_id, "missing_source_path": path}
            )

        # 4. Safety-relevant rows that lost score eligibility or disappeared.
        for key in sorted(before_elig - after_elig):
            row = next(
                (
                    r
                    for r in left.get("actives") or []
                    if f"{r.get('cid')}|{r.get('name')}|{r.get('path')}" == key
                ),
                {},
            )
            names = [
                str(row.get("name") or "").lower(),
                str(row.get("cid") or "").lower(),
                str(row.get("raw") or "").lower(),
            ]
            hit = next((safety[n] for n in names if n in safety), None)
            if hit:
                findings["lost_safety_rows"].append(
                    {"id": dsld_id, "row": row, "safety": hit}
                )
            if not (after_elig - before_elig):
                findings["de_eligibilised_without_provenance"].append(
                    {"id": dsld_id, "row": row, "ledger_omissions_after": after_counts.get("ledger_omissions")}
                )

        # 4b. Every active row dropped from the actives list must still be
        # represented in the label ledger (provenance), never silently gone.
        before_keys = {
            f"{r.get('cid')}|{r.get('name')}|{r.get('path')}"
            for r in left.get("actives") or []
        }
        after_keys = {
            f"{r.get('cid')}|{r.get('name')}|{r.get('path')}"
            for r in right.get("actives") or []
        }
        for key in sorted(before_keys - after_keys):
            row = next(
                (
                    r
                    for r in left.get("actives") or []
                    if f"{r.get('cid')}|{r.get('name')}|{r.get('path')}" == key
                ),
                {},
            )
            if str(row.get("path") or "") in after_paths:
                findings["rows_removed_from_actives_but_present_in_ledger"] += 1
            else:
                findings["rows_removed_from_actives_and_absent_from_ledger"] += 1

        # 5. A product that had a scored dose owner and no longer has one.
        if before_dosed and not after_dosed:
            findings["lost_dose_owners"].append(
                {
                    "id": dsld_id,
                    "name": item.get("name"),
                    "before_dosed": sorted(before_dosed),
                    "after_dosed": sorted(after_dosed),
                }
            )
        if len(before_elig) != len(after_elig):
            findings["eligibility_count_changes"].append(
                {"id": dsld_id, "before": len(before_elig), "after": len(after_elig)}
            )

    findings["row_ops"] = dict(findings["row_ops"])
    findings["family_product_counts"] = dict(findings["family_product_counts"])
    findings["summary"] = {
        key: len(value)
        for key, value in findings.items()
        if isinstance(value, list)
    }
    Path(args.out).write_text(
        json.dumps(findings, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(findings["summary"], indent=1))
    print(f"detail -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
