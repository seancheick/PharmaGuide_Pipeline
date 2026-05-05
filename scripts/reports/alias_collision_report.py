"""Generate a deterministic alias-collision triage report.

Scans inactive/additive reference data and reports:

1. Exact alias duplicates across entries.
2. Aliases that exactly match another entry's standard_name.

The output is intended for burn-down planning of legacy canonicalization
debt. It is not a runtime matcher and does not mutate source data.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports"
DATA_FILES = {
    "other_ingredients": ROOT / "data" / "other_ingredients.json",
    "harmful_additives": ROOT / "data" / "harmful_additives.json",
}

GENERIC_DESCRIPTOR_TOKENS = {
    "flavor",
    "flavors",
    "colour",
    "color",
    "colors",
    "coating",
    "capsule",
    "capsules",
    "shell",
    "descriptor",
    "preservative",
    "preservatives",
    "gum",
    "water",
    "extract",
    "blend",
    "glaze",
}


def _load_entries() -> list[dict]:
    entries: list[dict] = []
    for key, path in DATA_FILES.items():
        payload = json.loads(path.read_text())
        for entry in payload.get(key, []):
            item = dict(entry)
            item["_source_db"] = key
            entries.append(item)
    return entries


def _normalized_label(value: str) -> str:
    return value.strip().lower()


def _substantive_tokens(value: str) -> set[str]:
    chars = []
    for ch in value.lower():
        chars.append(ch if ch.isalnum() else " ")
    return {
        token
        for token in "".join(chars).split()
        if len(token) > 2 and token not in {"and", "the", "with", "from"}
    }


def _entry_ref(entry: dict) -> dict:
    external_ids = entry.get("external_ids") or {}
    return {
        "id": entry.get("id", ""),
        "standard_name": entry.get("standard_name", ""),
        "source_db": entry.get("_source_db", ""),
        "category": entry.get("category"),
        "additive_type": entry.get("additive_type"),
        "cui": entry.get("cui"),
        "unii": external_ids.get("unii"),
    }


def _has_within_source_ambiguity(refs: list[dict]) -> bool:
    by_source: dict[str, set[str]] = defaultdict(set)
    for ref in refs:
        by_source[ref["source_db"]].add(ref["id"])
    return any(len(ids) > 1 for ids in by_source.values())


def _classify_duplicate_severity(label: str, refs: list[dict]) -> str:
    std_names = {ref["standard_name"].lower() for ref in refs}
    tokens = _substantive_tokens(label)
    has_generic = bool(tokens & GENERIC_DESCRIPTOR_TOKENS)
    if not _has_within_source_ambiguity(refs):
        return "medium"
    if len(std_names) > 1 and not has_generic and len(tokens) >= 1:
        return "high"
    if len(std_names) > 2:
        return "high"
    return "medium" if has_generic else "high"


def _classify_alias_vs_standard_severity(label: str, alias_refs: list[dict], standard_refs: list[dict]) -> str:
    all_refs = alias_refs + standard_refs
    if not _has_within_source_ambiguity(all_refs):
        return "medium"
    tokens = _substantive_tokens(label)
    return "high" if tokens & GENERIC_DESCRIPTOR_TOKENS else "critical"


def compute_alias_collision_report() -> dict:
    entries = _load_entries()
    alias_map: dict[str, list[dict]] = defaultdict(list)
    standard_map: dict[str, list[dict]] = defaultdict(list)

    for entry in entries:
        ref = _entry_ref(entry)
        standard_name = _normalized_label(ref["standard_name"])
        if standard_name:
            standard_map[standard_name].append(ref)
        for alias in entry.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                alias_map[_normalized_label(alias)].append(ref)

    exact_alias_duplicates = []
    for label, refs in sorted(alias_map.items()):
        unique_ids = {ref["id"] for ref in refs}
        if len(unique_ids) < 2:
            continue
        exact_alias_duplicates.append(
            {
                "label": label,
                "severity": _classify_duplicate_severity(label, refs),
                "occurrence_count": len(unique_ids),
                "entries": sorted(refs, key=lambda item: (item["source_db"], item["id"])),
            }
        )

    alias_vs_standard_collisions = []
    for label, alias_refs in sorted(alias_map.items()):
        standard_refs = standard_map.get(label, [])
        all_ids = {ref["id"] for ref in alias_refs} | {ref["id"] for ref in standard_refs}
        if standard_refs and len(all_ids) > 1:
            alias_vs_standard_collisions.append(
                {
                    "label": label,
                    "severity": _classify_alias_vs_standard_severity(label, alias_refs, standard_refs),
                    "alias_entries": sorted(alias_refs, key=lambda item: (item["source_db"], item["id"])),
                    "standard_entries": sorted(standard_refs, key=lambda item: (item["source_db"], item["id"])),
                }
            )

    summary = {
        "exact_alias_duplicates": len(exact_alias_duplicates),
        "alias_vs_standard_collisions": len(alias_vs_standard_collisions),
        "critical": sum(1 for item in alias_vs_standard_collisions if item["severity"] == "critical"),
        "high": (
            sum(1 for item in exact_alias_duplicates if item["severity"] == "high")
            + sum(1 for item in alias_vs_standard_collisions if item["severity"] == "high")
        ),
        "medium": (
            sum(1 for item in exact_alias_duplicates if item["severity"] == "medium")
            + sum(1 for item in alias_vs_standard_collisions if item["severity"] == "medium")
        ),
    }

    return {
        "scope": ["other_ingredients", "harmful_additives"],
        "summary": summary,
        "exact_alias_duplicates": exact_alias_duplicates,
        "alias_vs_standard_collisions": alias_vs_standard_collisions,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Alias Collision Report",
        "",
        "## Summary",
        "",
        f"- Exact alias duplicates: {report['summary']['exact_alias_duplicates']}",
        f"- Alias-vs-standard collisions: {report['summary']['alias_vs_standard_collisions']}",
        f"- Critical: {report['summary']['critical']}",
        f"- High: {report['summary']['high']}",
        f"- Medium: {report['summary']['medium']}",
        "",
        "## Critical Alias-vs-Standard Collisions",
        "",
    ]

    critical = [item for item in report["alias_vs_standard_collisions"] if item["severity"] == "critical"]
    if not critical:
        lines.append("- None")
    else:
        for item in critical:
            lines.append(f"- `{item['label']}`")
            alias_entries = ", ".join(f"{ref['id']} ({ref['standard_name']})" for ref in item["alias_entries"])
            standard_entries = ", ".join(f"{ref['id']} ({ref['standard_name']})" for ref in item["standard_entries"])
            lines.append(f"  alias entries: {alias_entries}")
            lines.append(f"  standard entries: {standard_entries}")

    lines.extend([
        "",
        "## High-Risk Exact Alias Duplicates",
        "",
    ])
    high = [item for item in report["exact_alias_duplicates"] if item["severity"] == "high"]
    if not high:
        lines.append("- None")
    else:
        for item in high[:25]:
            refs = ", ".join(f"{ref['id']} ({ref['standard_name']})" for ref in item["entries"])
            lines.append(f"- `{item['label']}`: {refs}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate alias collision triage report.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for JSON + Markdown report (default: scripts/reports)",
    )
    parser.add_argument(
        "--prefix",
        default="alias_collision_report_latest",
        help="Filename prefix for generated report files",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 if any critical alias-vs-standard collisions exist.",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = compute_alias_collision_report()
    json_path = out_dir / f"{args.prefix}.json"
    md_path = out_dir / f"{args.prefix}.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    if args.fail_on_critical and report["summary"]["critical"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
