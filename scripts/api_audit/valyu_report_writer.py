from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPORT_DIR = SCRIPTS_ROOT / "api_audit" / "reports" / "valyu"


def _timestamp_slug(timestamp: str | None = None) -> str:
    if timestamp:
        return timestamp
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_report_paths(timestamp: str | None = None, output_dir: Path | None = None) -> dict[str, Path]:
    slug = _timestamp_slug(timestamp)
    root = output_dir or REPORT_DIR
    root.mkdir(parents=True, exist_ok=True)
    return {
        "raw_search_report": root / f"{slug}-raw-search-report.json",
        "review_queue": root / f"{slug}-review-queue.json",
        "summary": root / f"{slug}-summary.md",
    }


def render_summary(metadata: dict[str, Any], review_rows: list[dict[str, Any]]) -> str:
    counts = Counter(row.get("signal_type") for row in review_rows)
    strength_rank = {"high": 3, "medium": 2, "low": 1}
    sorted_rows = sorted(
        review_rows,
        key=lambda row: (
            strength_rank.get(str(row.get("signal_strength") or "").lower(), 0),
            str(row.get("entity_name") or ""),
        ),
        reverse=True,
    )
    lines = [
        "# Valyu Evidence Watchtower Summary",
        "",
        f"- Run timestamp: `{metadata.get('timestamp')}`",
        f"- Domain selection: `{metadata.get('mode')}`",
        f"- Targets scanned: `{metadata.get('targets_scanned', 0)}`",
        f"- Findings queued: `{len(review_rows)}`",
        "",
        "## Signal Counts",
        "",
    ]
    if counts:
        for key, value in sorted(counts.items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- No review findings")
    lines.extend(["", "## Highest-Priority Findings", ""])
    if sorted_rows:
        for row in sorted_rows[:10]:
            lines.append(
                f"- `{row.get('signal_type')}` | `{row.get('entity_name')}` | {row.get('reason') or 'No reason recorded'}"
            )
    else:
        lines.append("- No findings")
    return "\n".join(lines) + "\n"


def write_reports(
    metadata: dict[str, Any],
    raw_search_report: dict[str, Any],
    review_rows: list[dict[str, Any]],
    *,
    timestamp: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    paths = build_report_paths(timestamp=timestamp, output_dir=output_dir)
    paths["raw_search_report"].write_text(json.dumps(raw_search_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["review_queue"].write_text(json.dumps(review_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["summary"].write_text(render_summary(metadata, review_rows), encoding="utf-8")
    return paths
