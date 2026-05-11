"""
Phase 2 — Apply IQM alias migration.

Reads proposed_alias_migration.json (from Phase 0 audit) and executes:

  - For each MOVE finding:
      * If source_field == "form_name": remove the entire form from the marker
        IQM canonical, then relocate the form_name AND all its aliases to the
        target source-botanical canonical's aliases[].
      * If source_field == "alias": remove just the alias from the marker form's
        aliases[]; relocate the alias to the target source-botanical canonical.

  - For each QUALIFY finding: NO data file change. Cleaner Phase 3 update
    enforces the standardization predicate at match time. The alias text
    itself already encodes the standardization keyword.

  - Pre-creates the broccoli_sprout botanical canonical entry (the only one
    not already present in scripts/data/botanical_ingredients.json or
    standardized_botanicals.json).

  - Bumps scripts/data/ingredient_quality_map.json _metadata.schema_version
    from 5.3.0 → 5.4.0 (also handles legacy 5.0.0 / 5.2.0 by always writing 5.4.0).

  - Archives the pre-migration files at scripts/data/_archive/iqm_pre_identity_split/.

Run: python3 scripts/audits/identity_bioactivity_split/apply_migration.py
Dry run: python3 scripts/audits/identity_bioactivity_split/apply_migration.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "scripts" / "data"
IQM_PATH = DATA_DIR / "ingredient_quality_map.json"
BI_PATH = DATA_DIR / "botanical_ingredients.json"
SB_PATH = DATA_DIR / "standardized_botanicals.json"
MIGRATION_PATH = (
    REPO_ROOT / "scripts" / "audits" / "identity_bioactivity_split" / "proposed_alias_migration.json"
)
ARCHIVE_DIR = DATA_DIR / "_archive" / "iqm_pre_identity_split"
RUN_REPORT_PATH = (
    REPO_ROOT / "scripts" / "audits" / "identity_bioactivity_split" / "MIGRATION_RUN_REPORT.md"
)

NEW_IQM_SCHEMA = "5.4.0"

# Broccoli sprout canonical entry — only botanical missing from existing files.
# UMLS CUI verified via UMLS Metathesaurus (Brassica oleracea var. italica sprouts).
BROCCOLI_SPROUT_ENTRY = {
    "id": "broccoli_sprout",
    "standard_name": "Broccoli Sprout",
    "latin_name": "Brassica oleracea var. italica",
    "aliases": [
        "broccoli seed",
        "broccoli sprouts",
        "brassica oleracea italica sprouts",
    ],
    "category": "vegetable",
    "notes": (
        "Young broccoli plant sprouted from seed. Commercial source of glucoraphanin "
        "(precursor to sulforaphane). Sulforaphane is liberated by myrosinase enzyme "
        "during chewing or processing; standardized extracts declare glucoraphanin or "
        "sulforaphane content. Per identity/bioactivity split policy (Phase 2 of "
        "identity_bioactivity_split audit, 2026-05): credit sulforaphane Section C "
        "evidence only when label declares standardization."
    ),
    "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "external_ids": {},
    "cui": "C4521843",
    "functional_roles": [],
    "attributes": {
        "source_origin": "plant",
        "delivers_markers": ["sulforaphane"],
    },
}


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def normalize_alias(s: str) -> str:
    return (s or "").strip().lower()


def add_aliases_to_botanical_ingredients(bi: dict, botanical_id: str, new_aliases: list[str]) -> tuple[int, int]:
    """Returns (added_count, skipped_duplicate_count)."""
    for entry in bi["botanical_ingredients"]:
        if entry["id"] == botanical_id:
            existing_norm = {normalize_alias(a) for a in entry.get("aliases", [])}
            existing_norm.add(normalize_alias(entry.get("standard_name", "")))
            existing_norm.add(normalize_alias(entry.get("latin_name", "")))
            added = 0
            skipped = 0
            for a in new_aliases:
                if normalize_alias(a) in existing_norm:
                    skipped += 1
                    continue
                entry.setdefault("aliases", []).append(a)
                existing_norm.add(normalize_alias(a))
                added += 1
            return added, skipped
    raise KeyError(f"botanical_ingredients does not have id={botanical_id!r}")


def add_aliases_to_standardized_botanicals(sb: dict, botanical_id: str, new_aliases: list[str]) -> tuple[int, int]:
    for entry in sb["standardized_botanicals"]:
        if entry["id"] == botanical_id:
            existing_norm = {normalize_alias(a) for a in entry.get("aliases", [])}
            existing_norm.add(normalize_alias(entry.get("standard_name", "")))
            added = 0
            skipped = 0
            for a in new_aliases:
                if normalize_alias(a) in existing_norm:
                    skipped += 1
                    continue
                entry.setdefault("aliases", []).append(a)
                existing_norm.add(normalize_alias(a))
                added += 1
            return added, skipped
    raise KeyError(f"standardized_botanicals does not have id={botanical_id!r}")


def archive_pre_migration(dry_run: bool) -> None:
    if dry_run:
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for src in (IQM_PATH, BI_PATH, SB_PATH):
        dst = ARCHIVE_DIR / src.name
        shutil.copy2(src, dst)


def main(dry_run: bool) -> int:
    iqm = load_json(IQM_PATH)
    bi = load_json(BI_PATH)
    sb = load_json(SB_PATH)
    migration = load_json(MIGRATION_PATH)

    # Group moves: (marker_canonical, form_name) -> [moves]
    moves_by_form: dict[tuple[str, str], list[dict]] = defaultdict(list)
    qualifies: list[dict] = []
    for m in migration["migrations"]:
        cat = m["category"]
        if cat == "MOVE":
            moves_by_form[(m["marker_canonical"], m["form_name"])].append(m)
        elif cat == "QUALIFY":
            qualifies.append(m)

    # Verify broccoli_sprout entry not already present.
    bi_ids = {e["id"] for e in bi["botanical_ingredients"]}
    sb_ids = {e["id"] for e in sb["standardized_botanicals"]}
    if "broccoli_sprout" not in bi_ids and "broccoli_sprout" not in sb_ids:
        bi["botanical_ingredients"].append(BROCCOLI_SPROUT_ENTRY)
        bi_ids.add("broccoli_sprout")
        added_broccoli = True
    else:
        added_broccoli = False

    # Apply migrations
    report_lines: list[str] = []
    forms_deleted = 0
    aliases_removed = 0
    aliases_added_bi = 0
    aliases_added_sb = 0
    aliases_skipped_dup = 0

    for (marker, form_name), moves in sorted(moves_by_form.items()):
        target_botanical = moves[0]["to_canonical_id"]
        target_db = moves[0]["to_source_db"]
        # Sanity: all moves in this form-group should target the same botanical
        targets = {m["to_canonical_id"] for m in moves}
        if len(targets) > 1:
            raise ValueError(
                f"Form {marker}.{form_name} has moves targeting multiple botanicals: {targets}. Manual review required."
            )

        marker_entry = iqm.get(marker, {})
        forms = marker_entry.get("forms", {})
        if form_name not in forms:
            report_lines.append(f"- SKIP {marker}.{form_name}: form not found in IQM (already migrated?)")
            continue

        form_data = forms[form_name]
        form_name_moved = any(m["source_field"] == "form_name" for m in moves)
        aliases_to_remove = {m["offending_text"] for m in moves if m["source_field"] == "alias"}

        # Collect all alias texts to relocate (deduped, case-preserved by first occurrence)
        relocate: list[str] = []
        seen_norm: set[str] = set()
        if form_name_moved:
            relocate.append(form_name)
            seen_norm.add(normalize_alias(form_name))
            for a in form_data.get("aliases", []) or []:
                if normalize_alias(a) not in seen_norm:
                    relocate.append(a)
                    seen_norm.add(normalize_alias(a))
        else:
            for a in form_data.get("aliases", []) or []:
                if a in aliases_to_remove and normalize_alias(a) not in seen_norm:
                    relocate.append(a)
                    seen_norm.add(normalize_alias(a))

        if form_name_moved:
            # Delete the entire form
            del forms[form_name]
            forms_deleted += 1
            report_lines.append(
                f"- DELETE form `{marker}.{form_name}` (bio_score={form_data.get('bio_score')}); "
                f"relocate {len(relocate)} aliases to `{target_botanical}` ({target_db})"
            )
        else:
            # Remove specific aliases from the form
            before = len(form_data.get("aliases", []) or [])
            form_data["aliases"] = [
                a for a in (form_data.get("aliases", []) or []) if a not in aliases_to_remove
            ]
            removed = before - len(form_data["aliases"])
            aliases_removed += removed
            report_lines.append(
                f"- REMOVE {removed} alias(es) from `{marker}.{form_name}`; relocate to `{target_botanical}` ({target_db})"
            )

        # Append to target botanical
        if target_db == "botanical_ingredients":
            added, skipped = add_aliases_to_botanical_ingredients(bi, target_botanical, relocate)
            aliases_added_bi += added
            aliases_skipped_dup += skipped
        elif target_db == "standardized_botanicals":
            added, skipped = add_aliases_to_standardized_botanicals(sb, target_botanical, relocate)
            aliases_added_sb += added
            aliases_skipped_dup += skipped
        elif target_db == "MISSING_NEEDS_CREATION":
            # broccoli_sprout case — we already added the entry above; relocate aliases there
            added, skipped = add_aliases_to_botanical_ingredients(bi, target_botanical, relocate)
            aliases_added_bi += added
            aliases_skipped_dup += skipped
        else:
            raise ValueError(f"Unknown target_db {target_db!r}")

    # Bump IQM schema
    iqm.setdefault("_metadata", {})
    iqm["_metadata"]["schema_version"] = NEW_IQM_SCHEMA
    iqm["_metadata"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    iqm["_metadata"].setdefault("notes", "")
    note_suffix = " | identity_bioactivity_split: source-botanical aliases relocated to canonical homes (Phase 2)."
    if note_suffix.strip() not in iqm["_metadata"]["notes"]:
        iqm["_metadata"]["notes"] = (iqm["_metadata"]["notes"] + note_suffix).strip()

    # Bump botanical_ingredients schema if it doesn't already mention the split
    bi.setdefault("_metadata", {})
    bi_notes = bi["_metadata"].get("notes", "") or ""
    if "identity_bioactivity_split" not in bi_notes:
        bi["_metadata"]["notes"] = (
            bi_notes + " | identity_bioactivity_split: aliases from IQM marker canonicals relocated to source botanicals (Phase 2)."
        ).strip()
        bi["_metadata"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Summary
    summary = {
        "forms_deleted_from_iqm": forms_deleted,
        "aliases_removed_from_iqm_forms": aliases_removed,
        "aliases_added_to_botanical_ingredients": aliases_added_bi,
        "aliases_added_to_standardized_botanicals": aliases_added_sb,
        "aliases_skipped_as_duplicate": aliases_skipped_dup,
        "qualify_entries_unchanged_in_data": len(qualifies),
        "new_botanical_canonical_created": "broccoli_sprout" if added_broccoli else None,
    }

    if dry_run:
        print("=== DRY RUN — no files written ===")
        print(json.dumps(summary, indent=2))
        return 0

    archive_pre_migration(dry_run)
    save_json(IQM_PATH, iqm)
    save_json(BI_PATH, bi)
    save_json(SB_PATH, sb)

    # Run report
    lines: list[str] = []
    lines.append("# Phase 2 Migration Run Report")
    lines.append("")
    lines.append(f"_Run: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for k, v in summary.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Per-form actions")
    lines.append("")
    lines.extend(report_lines)
    lines.append("")
    lines.append("## Archive")
    lines.append("")
    lines.append(f"Pre-migration snapshots: `{ARCHIVE_DIR.relative_to(REPO_ROOT)}/`")
    RUN_REPORT_PATH.write_text("\n".join(lines))

    print("=== Migration applied ===")
    print(json.dumps(summary, indent=2))
    print(f"Run report: {RUN_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Compute migration without writing files")
    args = parser.parse_args()
    raise SystemExit(main(dry_run=args.dry_run))
