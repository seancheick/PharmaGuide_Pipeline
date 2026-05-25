#!/usr/bin/env python3
from __future__ import annotations
"""Report runtime-equivalent UNII same-tier conflicts.

The normalizer builds a UNII lookup with priority tiers. Cross-tier collisions
are expected: the safer or more authoritative tier wins. Same-tier collisions
emit a runtime warning because first-write wins inside a tier. This scanner is
the report-only companion for that warning.

It intentionally does not call FDA APIs or edit data. It classifies the local
reference-data shape so reviewers can distinguish benign IQM parent/form
duplicates from genuinely suspicious same-tier claims.
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PLACEHOLDER_UNIIS = frozenset({"", "0", "1"})

TIER_NAMES = {
    1: "banned_recalled",
    2: "allergens",
    3: "harmful_additives",
    4: "ingredient_quality_map",
    5: "standardized_botanicals",
    6: "botanical_ingredients",
    7: "other_ingredients_lookup",
    8: "proprietary_blends",
    9: "other_ingredients",
}


@dataclass(frozen=True)
class UniiRecord:
    tier: int
    tier_name: str
    source: str
    file: str
    entry_id: str
    standard_name: str
    unii: str
    parent_id: str | None = None
    parent_standard_name: str | None = None


@dataclass(frozen=True)
class SameTierGroup:
    tier: int
    tier_name: str
    unii: str
    severity: str
    classification: str
    action: str
    reason: str
    records: tuple[UniiRecord, ...]


def normalize_unii(value: Any) -> str | None:
    """Canonicalize a UNII string and reject DSLD placeholders."""
    if not isinstance(value, str):
        return None
    canon = value.strip().upper()
    if canon in PLACEHOLDER_UNIIS:
        return None
    if len(canon) != 10 or not canon.isalnum():
        return None
    return canon


def extract_unii(entry: dict[str, Any]) -> str | None:
    if not isinstance(entry, dict):
        return None
    external_ids = entry.get("external_ids") or {}
    if isinstance(external_ids, dict):
        unii = normalize_unii(external_ids.get("unii"))
        if unii:
            return unii
    return normalize_unii(entry.get("unii"))


def _norm_name(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\([^)]*\)", " ", value.lower())
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_runtime_priority_context(repo_root: Path):
    """Load the normalizer's exact-key priority context.

    Same-tier warnings use the payload priority from `_fast_exact_lookup`, not
    just the file a record came from. This matters for entries whose standard
    name is already claimed by a higher-priority tier. The audit stays
    read-only; this context is only used to mirror runtime priority numbers.
    """
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    logging.getLogger("enhanced_normalizer").setLevel(logging.ERROR)
    from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: WPS433

    normalizer = EnhancedDSLDNormalizer()
    return normalizer.matcher.preprocess_text, normalizer._fast_exact_lookup


def _effective_priority(
    standard_name: str,
    default_priority: int,
    preprocess_text,
    fast_exact_lookup: dict[str, dict[str, Any]],
) -> int:
    processed = preprocess_text(standard_name) if standard_name else ""
    payload = fast_exact_lookup.get(processed) if processed else None
    if isinstance(payload, dict):
        return int(payload.get("priority", default_priority))
    return default_priority


def _iter_banned_records(repo_root: Path, preprocess_text, fast_exact_lookup) -> Iterable[UniiRecord]:
    path = repo_root / "scripts/data/banned_recalled_ingredients.json"
    blob = _load_json(path)
    for section_name, value in blob.items():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            unii = extract_unii(entry)
            if not unii:
                continue
            entry_id = entry.get("id") or entry.get("standard_name") or f"{section_name}:<unnamed>"
            standard_name = entry.get("standard_name") or entry_id
            priority = _effective_priority(str(standard_name), 1, preprocess_text, fast_exact_lookup)
            yield UniiRecord(
                tier=priority,
                tier_name=TIER_NAMES.get(priority, f"tier_{priority}"),
                source="banned",
                file=path.name,
                entry_id=str(entry_id),
                standard_name=str(standard_name),
                unii=unii,
            )


def _iter_iqm_records(repo_root: Path, preprocess_text, fast_exact_lookup) -> Iterable[UniiRecord]:
    path = repo_root / "scripts/data/ingredient_quality_map.json"
    blob = _load_json(path)
    for parent_id, parent_data in blob.items():
        if parent_id.startswith("_") or not isinstance(parent_data, dict):
            continue
        parent_standard_name = parent_data.get("standard_name") or parent_id
        priority = _effective_priority(str(parent_standard_name), 4, preprocess_text, fast_exact_lookup)
        parent_unii = extract_unii(parent_data)
        if parent_unii:
            yield UniiRecord(
                tier=priority,
                tier_name=TIER_NAMES.get(priority, f"tier_{priority}"),
                source="iqm_parent",
                file=path.name,
                entry_id=parent_id,
                standard_name=str(parent_standard_name),
                unii=parent_unii,
                parent_id=parent_id,
                parent_standard_name=str(parent_standard_name),
            )
        forms = parent_data.get("forms") or {}
        if not isinstance(forms, dict):
            continue
        for form_name, form_data in forms.items():
            if not isinstance(form_data, dict):
                continue
            form_unii = extract_unii(form_data)
            if not form_unii:
                continue
            yield UniiRecord(
                tier=priority,
                tier_name=TIER_NAMES.get(priority, f"tier_{priority}"),
                source="iqm_form",
                file=path.name,
                entry_id=f"{parent_id}.forms[{form_name}]",
                standard_name=str(form_name),
                unii=form_unii,
                parent_id=parent_id,
                parent_standard_name=str(parent_standard_name),
            )


def _iter_list_records(
    repo_root: Path,
    file_name: str,
    list_key: str,
    tier: int,
    source: str,
    preprocess_text,
    fast_exact_lookup: dict[str, dict[str, Any]],
    *,
    use_effective_priority: bool = True,
) -> Iterable[UniiRecord]:
    path = repo_root / "scripts/data" / file_name
    blob = _load_json(path)
    entries = blob.get(list_key, [])
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        unii = extract_unii(entry)
        if not unii:
            continue
        entry_id = entry.get("id") or entry.get("standard_name") or "<unnamed>"
        standard_name = entry.get("standard_name") or entry_id
        if use_effective_priority:
            priority = _effective_priority(str(standard_name), tier, preprocess_text, fast_exact_lookup)
        else:
            priority = tier
        yield UniiRecord(
            tier=priority,
            tier_name=TIER_NAMES.get(priority, f"tier_{priority}"),
            source=source,
            file=file_name,
            entry_id=str(entry_id),
            standard_name=str(standard_name),
            unii=unii,
        )


def collect_unii_records(repo_root: Path) -> list[UniiRecord]:
    preprocess_text, fast_exact_lookup = _load_runtime_priority_context(repo_root)
    records: list[UniiRecord] = []
    records.extend(_iter_banned_records(repo_root, preprocess_text, fast_exact_lookup))
    records.extend(_iter_iqm_records(repo_root, preprocess_text, fast_exact_lookup))
    records.extend(
        _iter_list_records(
            repo_root,
            "standardized_botanicals.json",
            "standardized_botanicals",
            tier=5,
            source="standardized_botanical",
            preprocess_text=preprocess_text,
            fast_exact_lookup=fast_exact_lookup,
        )
    )
    records.extend(
        _iter_list_records(
            repo_root,
            "botanical_ingredients.json",
            "botanical_ingredients",
            tier=6,
            source="botanical",
            preprocess_text=preprocess_text,
            fast_exact_lookup=fast_exact_lookup,
        )
    )
    records.extend(
        _iter_list_records(
            repo_root,
            "other_ingredients.json",
            "other_ingredients",
            tier=9,
            source="other_ingredient",
            preprocess_text=preprocess_text,
            fast_exact_lookup=fast_exact_lookup,
            use_effective_priority=False,
        )
    )
    return records


def _classify_group(records: tuple[UniiRecord, ...]) -> tuple[str, str, str, str]:
    tier = records[0].tier
    parent_ids = {record.parent_id for record in records if record.parent_id}
    names = {_norm_name(record.standard_name) for record in records if _norm_name(record.standard_name)}

    if tier == 4 and len(parent_ids) == 1:
        return (
            "info",
            "iqm_same_parent_parent_form",
            "suppress_runtime_warning_candidate",
            "IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.",
        )
    if tier == 4 and len(parent_ids) > 1:
        return (
            "high_review",
            "iqm_cross_parent_same_unii",
            "review_data_model_or_exonerate",
            "Same UNII appears under different IQM parents/forms at the same priority tier.",
        )
    if len(names) == 1:
        return (
            "review",
            "same_tier_duplicate_name",
            "review_duplicate_or_alias_model",
            "Same-tier records have the same normalized name; may be duplicate modeling or alias drift.",
        )
    return (
        "high_review",
        "same_tier_different_names",
        "verify_unii_assignment",
        "Same-tier records have materially different names; first-write wins at runtime until reviewed.",
    )


def find_same_tier_groups(records: list[UniiRecord]) -> list[SameTierGroup]:
    grouped: dict[tuple[int, str], list[UniiRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.tier, record.unii)].append(record)

    out: list[SameTierGroup] = []
    for (tier, unii), members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        records_tuple = tuple(sorted(members, key=lambda r: (r.source, r.entry_id)))
        severity, classification, action, reason = _classify_group(records_tuple)
        out.append(
            SameTierGroup(
                tier=tier,
                tier_name=TIER_NAMES.get(tier, f"tier_{tier}"),
                unii=unii,
                severity=severity,
                classification=classification,
                action=action,
                reason=reason,
                records=records_tuple,
            )
        )
    return out


def render_markdown(records: list[UniiRecord], groups: list[SameTierGroup]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    severity_counts = Counter(group.severity for group in groups)
    class_counts = Counter(group.classification for group in groups)
    tier_counts = Counter(group.tier_name for group in groups)

    lines: list[str] = [
        "# UNII Same-Tier Conflict Audit",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope",
        "",
        "This is a read-only scanner for the runtime warning emitted by "
        "`EnhancedDSLDNormalizer._build_unii_to_payload_lookup`: same UNII, "
        "same lookup-priority tier, multiple records. Cross-tier collisions are "
        "intentionally excluded because runtime priority order resolves them.",
        "",
        "Tier labels below are **effective runtime priorities** from the "
        "normalizer's fast exact lookup for active/safety sources. "
        "`other_ingredients.json` UNII records intentionally remain in the "
        "low-priority other-ingredient tier because inactive/excipient UNII "
        "recognition is handled by a separate context-aware enricher index.",
        "",
        "No reference data was changed by this audit.",
        "",
        "## Summary",
        "",
        f"- UNII-bearing records scanned: **{len(records)}**",
        f"- Same-tier UNII groups: **{len(groups)}**",
        "",
        "| Severity | Groups |",
        "|---|---:|",
    ]
    for severity in ("high_review", "review", "info"):
        lines.append(f"| {severity} | {severity_counts.get(severity, 0)} |")
    lines.extend(["", "| Tier | Groups |", "|---|---:|"])
    for tier_name, count in sorted(tier_counts.items()):
        lines.append(f"| {tier_name} | {count} |")
    lines.extend(["", "| Classification | Groups |", "|---|---:|"])
    for classification, count in sorted(class_counts.items()):
        lines.append(f"| {classification} | {count} |")

    def section(title: str, selected: list[SameTierGroup]) -> None:
        lines.extend(["", f"## {title}", ""])
        if not selected:
            lines.extend(["_None found._", ""])
            return
        for group in selected:
            lines.append(
                f"### `{group.unii}` — tier {group.tier} `{group.tier_name}` "
                f"({group.classification}, {group.severity})"
            )
            lines.append("")
            lines.append(f"- Action: `{group.action}`")
            lines.append(f"- Reason: {group.reason}")
            for record in group.records:
                parent = f", parent=`{record.parent_id}`" if record.parent_id else ""
                lines.append(
                    f"- `{record.file}` → `{record.entry_id}` "
                    f"({record.source}; {record.standard_name}{parent})"
                )
            lines.append("")

    section(
        "High-Review Groups",
        [group for group in groups if group.severity == "high_review"],
    )
    section(
        "Review Groups",
        [group for group in groups if group.severity == "review"],
    )
    section(
        "Info / Suppression-Candidate Groups",
        [group for group in groups if group.severity == "info"],
    )

    return "\n".join(lines)


def write_json_report(path: Path, records: list[UniiRecord], groups: list[SameTierGroup]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "record_count": len(records),
        "same_tier_group_count": len(groups),
        "severity_counts": dict(Counter(group.severity for group in groups)),
        "classification_counts": dict(Counter(group.classification for group in groups)),
        "tier_counts": dict(Counter(group.tier_name for group in groups)),
        "groups": [
            {
                **{k: v for k, v in asdict(group).items() if k != "records"},
                "records": [asdict(record) for record in group.records],
            }
            for group in groups
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit for runtime-equivalent UNII same-tier conflicts."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root; default: cwd")
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for markdown + JSON reports; default: reports/",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional timestamp suffix for deterministic report filenames.",
    )
    parser.add_argument(
        "--fail-on-high-review",
        action="store_true",
        help="Exit 1 if any high_review groups are found. Default is report-only exit 0.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    records = collect_unii_records(repo_root)
    groups = find_same_tier_groups(records)
    timestamp = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"unii_same_tier_conflicts_{timestamp}.md"
    json_path = output_dir / f"unii_same_tier_conflicts_{timestamp}.json"
    md_path.write_text(render_markdown(records, groups), encoding="utf-8")
    write_json_report(json_path, records, groups)

    severity_counts = Counter(group.severity for group in groups)
    print(f"Reports written: {md_path} and {json_path}")
    print(
        "UNII same-tier groups: "
        f"{len(groups)} total; "
        f"{severity_counts.get('high_review', 0)} high_review, "
        f"{severity_counts.get('review', 0)} review, "
        f"{severity_counts.get('info', 0)} info."
    )
    if args.fail_on_high_review and severity_counts.get("high_review", 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
