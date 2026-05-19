#!/usr/bin/env python3
"""Diff two scored/exported PharmaGuide outputs by DSLD ID.

Supports scored batch JSON directories and final export detail_blobs. Intended
for release-candidate review before syncing rebuilt catalog artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "scripts" / "api_audit" / "reports"


def _load_db_scores(root: Path) -> dict[str, dict[str, Any]]:
    """If `root` contains `pharmaguide_core.db`, pull score+verdict per dsld_id.

    Shipped detail_blobs don't carry score_100_equivalent at top level — the
    final score lives in the SQLite DB. Without this, score_changed reports 0
    even when the catalog moved by ±10 points (real bug surfaced by RC review).
    """
    db_path = root / "pharmaguide_core.db" if root.is_dir() else None
    if db_path is None or not db_path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        for r in con.execute(
            "SELECT dsld_id, score_100_equivalent, verdict FROM products_core"
        ):
            out[str(r["dsld_id"])] = {
                "score_100_equivalent": r["score_100_equivalent"],
                "verdict": r["verdict"],
            }
    finally:
        con.close()
    return out


def _iter_json_records(root: Path) -> list[dict[str, Any]]:
    """Read scored products from a directory or single JSON file."""
    files: list[Path]
    if root.is_file():
        files = [root]
    else:
        detail_blobs = root / "detail_blobs"
        search_root = detail_blobs if detail_blobs.exists() else root
        files = sorted(search_root.rglob("*.json"))

    records: list[dict[str, Any]] = []
    for path in files:
        if "/reports/" in path.as_posix() or path.name in {"detail_index.json", "scoring_summary.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, list):
            records.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            records.append(payload)
    return records


def _product_id(record: dict[str, Any]) -> str | None:
    value = record.get("dsld_id") or record.get("id")
    return str(value) if value is not None and str(value) else None


def _product_score(record: dict[str, Any]) -> float | None:
    for key in ("score_100_equivalent", "display_100", "score_display_100_equivalent"):
        value = record.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _product_b4a(record: dict[str, Any]) -> float | None:
    breakdown = record.get("breakdown")
    if isinstance(breakdown, dict):
        b_section = breakdown.get("B")
        if isinstance(b_section, dict) and isinstance(b_section.get("B4a"), (int, float)):
            return float(b_section["B4a"])

    section_breakdown = record.get("section_breakdown")
    if isinstance(section_breakdown, dict):
        safety = section_breakdown.get("safety_purity")
        if isinstance(safety, dict):
            sub = safety.get("sub")
            if isinstance(sub, dict) and isinstance(sub.get("B4a"), (int, float)):
                return float(sub["B4a"])
    return None


def _index_records(root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in _iter_json_records(root):
        dsld_id = _product_id(record)
        if not dsld_id:
            continue
        out[dsld_id] = record
    return out


def build_delta_rows(before: Path, after: Path) -> list[dict[str, Any]]:
    before_index = _index_records(before)
    after_index = _index_records(after)
    # Pull score + verdict from pharmaguide_core.db (authoritative) when
    # available. detail_blob payloads don't carry the rolled-up score, so the
    # blob-only path returns score_changed=0 even on real moves. Falls back to
    # blob-only fields if the DB isn't present.
    before_db = _load_db_scores(before)
    after_db = _load_db_scores(after)
    all_ids = sorted(set(before_index) | set(after_index), key=lambda x: (not x.isdigit(), x))

    rows: list[dict[str, Any]] = []
    for dsld_id in all_ids:
        old = before_index.get(dsld_id)
        new = after_index.get(dsld_id)
        old_db = before_db.get(dsld_id, {})
        new_db = after_db.get(dsld_id, {})
        old_score = old_db.get("score_100_equivalent") if old_db else _product_score(old or {})
        new_score = new_db.get("score_100_equivalent") if new_db else _product_score(new or {})
        old_b4a = _product_b4a(old or {})
        new_b4a = _product_b4a(new or {})
        old_verdict = old_db.get("verdict") if old_db else (old or {}).get("verdict")
        new_verdict = new_db.get("verdict") if new_db else (new or {}).get("verdict")
        name_record = new or old or {}
        rows.append(
            {
                "dsld_id": dsld_id,
                "status": "added" if old is None else "removed" if new is None else "changed",
                "brand": name_record.get("brand_name") or name_record.get("brandName") or "",
                "product": name_record.get("product_name") or name_record.get("productName") or "",
                "score_before": old_score,
                "score_after": new_score,
                "score_delta": _delta(old_score, new_score),
                "b4a_before": old_b4a,
                "b4a_after": new_b4a,
                "b4a_delta": _delta(old_b4a, new_b4a),
                "verdict_before": old_verdict,
                "verdict_after": new_verdict,
            }
        )
    return rows


def _delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(after - before, 4)


def write_reports(rows: list[dict[str, Any]], out_dir: Path, prefix: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{prefix}_{timestamp}"
    json_path = out_dir / f"{base}.json"
    csv_path = out_dir / f"{base}.csv"
    md_path = out_dir / f"{base}.md"

    summary = _summary(rows)
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n", encoding="utf-8")

    fieldnames = [
        "dsld_id",
        "status",
        "brand",
        "product",
        "score_before",
        "score_after",
        "score_delta",
        "b4a_before",
        "b4a_after",
        "b4a_delta",
        "verdict_before",
        "verdict_after",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    top_score = sorted(
        [r for r in rows if isinstance(r.get("score_delta"), (int, float))],
        key=lambda r: abs(r["score_delta"]),
        reverse=True,
    )[:20]
    top_b4a = sorted(
        [r for r in rows if isinstance(r.get("b4a_delta"), (int, float))],
        key=lambda r: abs(r["b4a_delta"]),
        reverse=True,
    )[:20]
    md_path.write_text(_markdown(summary, top_score, top_b4a), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score_deltas = [r["score_delta"] for r in rows if isinstance(r.get("score_delta"), (int, float))]
    b4a_deltas = [r["b4a_delta"] for r in rows if isinstance(r.get("b4a_delta"), (int, float))]

    # Comparable verdict transitions only — counts rows where the product is in
    # BOTH old and new builds AND verdict differs. Excludes added/removed rows
    # (which look like "verdict changed from None" but are just ID churn from
    # UPC dedupe).  See Codex's RC review note: "189 count is easy to misread."
    comparable_rows = [r for r in rows if r["status"] == "changed"]
    verdict_transitions: Counter = Counter()
    for r in comparable_rows:
        v_old, v_new = r.get("verdict_before"), r.get("verdict_after")
        if v_old and v_new and v_old != v_new:
            verdict_transitions[(v_old, v_new)] += 1
    verdict_changed_comparable = sum(verdict_transitions.values())

    return {
        "total_rows": len(rows),
        "added": sum(1 for r in rows if r["status"] == "added"),
        "removed": sum(1 for r in rows if r["status"] == "removed"),
        "compared_in_both": len(comparable_rows),
        "score_changed": sum(1 for d in score_deltas if d != 0),
        "b4a_changed": sum(1 for d in b4a_deltas if d != 0),
        # Verdict accounting — comparable only. ID churn (added/removed) is
        # reported separately above so consumers don't misread the total.
        "verdict_changed_comparable": verdict_changed_comparable,
        "verdict_transitions": {f"{o} -> {n}": c for (o, n), c in verdict_transitions.most_common()},
        "max_abs_score_delta": max((abs(d) for d in score_deltas), default=0),
        "max_abs_b4a_delta": max((abs(d) for d in b4a_deltas), default=0),
    }


def _markdown(summary: dict[str, Any], top_score: list[dict[str, Any]], top_b4a: list[dict[str, Any]]) -> str:
    transitions = summary.get("verdict_transitions", {})
    transition_lines = (
        [f"  - `{t}`: **{c}**" for t, c in transitions.items()]
        if transitions
        else ["  - (none)"]
    )
    lines = [
        "# Score Delta Report",
        "",
        "## Summary",
        "",
        f"- Total rows in report: **{summary['total_rows']}**",
        f"- Added (in new only — usually UPC dedupe churn, NOT a transition): **{summary['added']}**",
        f"- Removed (in old only — same): **{summary['removed']}**",
        f"- Compared in both builds: **{summary.get('compared_in_both', summary['total_rows'] - summary['added'] - summary['removed'])}**",
        f"- Score changed (comparable rows with non-zero delta): **{summary['score_changed']}**",
        f"- B4a changed (comparable rows with non-zero delta): **{summary['b4a_changed']}**",
        f"- **Verdict transitions (comparable rows only)**: **{summary.get('verdict_changed_comparable', 0)}**",
        *transition_lines,
        f"- Max |score delta|: **{summary['max_abs_score_delta']}**",
        f"- Max |B4a delta|: **{summary['max_abs_b4a_delta']}**",
        "",
        "> Verdict-transition count is **comparable rows only** — added/removed are reported separately so consumers don't confuse ID churn with real verdict regressions.",
        "",
        "## Top Score Movers",
        "",
    ]
    lines.extend(_row_lines(top_score, "score_delta", "score_before", "score_after"))
    lines.extend(["", "## Top B4a Movers", ""])
    lines.extend(_row_lines(top_b4a, "b4a_delta", "b4a_before", "b4a_after"))
    return "\n".join(lines) + "\n"


def _row_lines(rows: list[dict[str, Any]], delta_key: str, before_key: str, after_key: str) -> list[str]:
    if not rows:
        return ["- No comparable deltas."]
    return [
        f"- `{r['dsld_id']}` **{r['brand']}** — {r['product']}: "
        f"{r[before_key]} → {r[after_key]} (Δ {r[delta_key]})"
        for r in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff two PharmaGuide scored outputs by DSLD ID.")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prefix", default="score_delta_report")
    args = parser.parse_args()

    rows = build_delta_rows(args.before, args.after)
    paths = write_reports(rows, args.out, args.prefix)
    print("Wrote:")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")


if __name__ == "__main__":
    main()
