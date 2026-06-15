#!/usr/bin/env python3
"""V4 scoring-health audit.

Reads the current final DB plus detail blobs and writes:
  - a 100-product markdown/csv sample
  - a grouped zero-evidence audit by canonical identity

The anomaly classification intentionally mirrors
scripts.dashboard.views.scoring_integrity so the report and dashboard do not
drift.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dashboard.views.scoring_integrity import classify_zero_pillar  # noqa: E402

PILLARS = (
    ("formulation", "Formulation", 20),
    ("dose", "Dose", 20),
    ("evidence", "Evidence", 20),
    ("transparency", "Transparency", 15),
    ("verification", "Verification", 15),
    ("safety_hygiene", "Safety/Hygiene", 10),
)


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_blob(blob_dir: Path, dsld_id: str) -> dict[str, Any]:
    path = blob_dir / f"{dsld_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _pillar_score(pillars: dict[str, Any], key: str) -> float | None:
    return _num(_safe_dict(pillars.get(key)).get("score"))


def _assessment(row: dict[str, Any], pillars: dict[str, Any]) -> tuple[str, str]:
    total = _num(row.get("quality_score_v4_100"))
    scores = {key: _pillar_score(pillars, key) for key, _label, _mx in PILLARS}
    if total is None or any(value is None for value in scores.values()):
        return "data", "missing total or pillar blob"
    pillar_sum = round(sum(value or 0.0 for value in scores.values()), 1)
    if abs(pillar_sum - total) > 0.1:
        return "bug", f"pillars sum {pillar_sum:.1f} != total {total:.1f}"
    zeroes = []
    for key, label, _mx in PILLARS:
        if scores[key] == 0:
            zeroes.append(f"{label}:{classify_zero_pillar(label, row)}")
    if zeroes:
        return "check", "; ".join(zeroes)
    return "normal", "pillars coherent"


def _weakest_pillar(pillars: dict[str, Any]) -> str:
    weakest: tuple[float, str] | None = None
    for key, label, mx in PILLARS:
        score = _pillar_score(pillars, key)
        if score is None:
            continue
        frac = score / mx if mx else 0.0
        reason = _safe_dict(pillars.get(key)).get("reason") or ""
        text = f"{label} {score:.1f}/{mx}: {reason}"
        if weakest is None or frac < weakest[0]:
            weakest = (frac, text)
    return weakest[1] if weakest else "no pillar data"


def _ingredient_keys(blob: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for row in _safe_list(blob.get("ingredients")):
        if not isinstance(row, dict):
            continue
        key = str(row.get("canonical_id") or row.get("standard_name") or row.get("name") or "").strip()
        if key:
            keys.append(key)
    return keys


def load_rows(db_path: Path) -> list[dict[str, Any]]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT dsld_id, product_name, brand_name, verdict, safety_verdict,
                   quality_score_v4_100, quality_score_status, v4_module,
                   v4_confidence, pillar_evidence_v4
            FROM products_core
            ORDER BY (quality_score_v4_100 IS NULL), quality_score_v4_100 DESC, dsld_id
            """
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def write_sample(rows: list[dict[str, Any]], blob_dir: Path, out_md: Path, out_csv: Path, limit: int) -> None:
    sampled = rows[:limit]
    csv_rows: list[dict[str, Any]] = []
    lines = [
        "# V4 Scoring Health Sample",
        "",
        "| # | Product | id | Score | Route | Conf | Weakest pillar | Assessment |",
        "|---:|---|---:|---:|---|---|---|---|",
    ]
    for idx, row in enumerate(sampled, 1):
        dsld_id = str(row["dsld_id"])
        blob = _load_blob(blob_dir, dsld_id)
        pillars = _safe_dict(blob.get("quality_pillars_v4"))
        status, note = _assessment(row, pillars)
        weakest = _weakest_pillar(pillars)
        lines.append(
            f"| {idx} | {row.get('product_name','')} | {dsld_id} | "
            f"{row.get('quality_score_v4_100')} | {row.get('v4_module','')} | "
            f"{row.get('v4_confidence','')} | {weakest} | {status}: {note} |"
        )
        csv_rows.append({
            **row,
            "weakest_pillar": weakest,
            "assessment": status,
            "assessment_note": note,
        })
    out_md.write_text("\n".join(lines) + "\n")
    with out_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()) if csv_rows else [])
        if csv_rows:
            writer.writeheader()
            writer.writerows(csv_rows)


def write_zero_evidence_audit(rows: list[dict[str, Any]], blob_dir: Path, out_path: Path) -> None:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "products": 0,
        "modules": Counter(),
        "match_counts": Counter(),
        "examples": [],
    })
    for row in rows:
        if row.get("quality_score_status") != "scored":
            continue
        if _num(row.get("pillar_evidence_v4")) != 0.0:
            continue
        dsld_id = str(row["dsld_id"])
        blob = _load_blob(blob_dir, dsld_id)
        evidence = _safe_dict(blob.get("evidence_data"))
        match_count = int(_num(evidence.get("match_count")) or 0)
        keys = _ingredient_keys(blob) or ["unknown"]
        for key in keys:
            bucket = grouped[key]
            bucket["products"] += 1
            bucket["modules"][row.get("v4_module") or ""] += 1
            bucket["match_counts"][match_count] += 1
            if len(bucket["examples"]) < 5:
                bucket["examples"].append(f"{dsld_id} {row.get('product_name','')}")

    lines = [
        "# V4 Zero-Evidence Grouped Audit",
        "",
        "| Canonical / identity | Products | Modules | Match counts | Examples |",
        "|---|---:|---|---|---|",
    ]
    for key, bucket in sorted(grouped.items(), key=lambda item: item[1]["products"], reverse=True):
        modules = ", ".join(f"{name}:{count}" for name, count in bucket["modules"].most_common())
        match_counts = ", ".join(f"{name}:{count}" for name, count in bucket["match_counts"].most_common())
        examples = "<br>".join(bucket["examples"])
        lines.append(f"| {key} | {bucket['products']} | {modules} | {match_counts} | {examples} |")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "scripts/final_db_output/pharmaguide_core.db")
    parser.add_argument("--blob-dir", type=Path, default=REPO_ROOT / "scripts/final_db_output/detail_blobs")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "scripts/audits")
    parser.add_argument("--sample-size", type=int, default=100)
    args = parser.parse_args()

    rows = load_rows(args.db)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_sample(
        rows,
        args.blob_dir,
        args.out_dir / "v4_scoring_health_sample_100.md",
        args.out_dir / "v4_scoring_health_sample_100.csv",
        args.sample_size,
    )
    write_zero_evidence_audit(
        rows,
        args.blob_dir,
        args.out_dir / "v4_zero_evidence_grouped_audit.md",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
