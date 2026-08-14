#!/usr/bin/env python3
"""
validate_form_notes_export.py — Gate B for consumer form notes.

Gate A (``validate_iqm_consumer_notes`` in build_final_db.py) proves a human
reviewed each ``consumer_note`` in the source map. It cannot prove what reached
the device: an emitted blob carries no ``consumer_note_review``. This validator
closes that half by scanning the emitted detail blobs themselves.

Checks canonical ``display_ingredients[].analysis`` and legacy
``ingredients[]`` form-note fields for:

  * internal audit text, safety language, or marketing language
  * notes longer than the export ceiling
  * placement errors on canonical rows: a note without a score or
    ``score_included=true``
  * a preview without a full note or a preview that differs from the exact first
    sentence of its note

The legacy ``ingredients[].notes`` workspace field is deliberately NOT checked.
It is expected to contain PMIDs and audit trails. Its separately exported
``form_note`` fields are checked, however, so every new consumer-copy surface
has the same content and preview protection.

Fail-loud: any violation exits non-zero so the release train halts.

Usage:
  python3 scripts/validate_form_notes_export.py
  python3 scripts/validate_form_notes_export.py --blobs-dir scripts/dist/detail_blobs
  python3 scripts/validate_form_notes_export.py --limit 500   # spot check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_final_db import (  # noqa: E402
    _FORM_NOTE_INTERNAL_RE,
    _FORM_NOTE_MARKETING_RE,
    _FORM_NOTE_MAX_CHARS,
    _FORM_NOTE_SAFETY_RE,
    _FORM_NOTE_SENTENCE_RE,
)
from iqm_form_evidence import validate_exported_form_evidence  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLOBS_DIR = REPO_ROOT / "scripts" / "dist" / "detail_blobs"


def _check_form_note(note: Any, preview: Any, label: str) -> List[str]:
    """Content and exact-preview violations for one exported form note."""
    if note is None and preview is None:
        return []

    problems: List[str] = []

    if note is None:
        return [f"{label}: form_note_preview present without form_note"]
    if not isinstance(note, str) or not note.strip():
        return [f"{label}: form_note present but empty"]

    if len(note) > _FORM_NOTE_MAX_CHARS:
        problems.append(
            f"{label}: form_note is {len(note)} chars (max {_FORM_NOTE_MAX_CHARS})"
        )
    for kind, pattern in (
        ("internal audit text", _FORM_NOTE_INTERNAL_RE),
        ("safety language", _FORM_NOTE_SAFETY_RE),
        ("marketing language", _FORM_NOTE_MARKETING_RE),
    ):
        match = pattern.search(note)
        if match:
            problems.append(f"{label}: form_note contains {kind} ({match.group(0)!r})")

    if not isinstance(preview, str) or not preview.strip():
        problems.append(f"{label}: form_note without form_note_preview")
    else:
        expected_preview = _FORM_NOTE_SENTENCE_RE.split(note)[0].strip() or note
        if preview != expected_preview:
            problems.append(
                f"{label}: form_note_preview is not the exact first sentence "
                "of form_note"
            )

    return problems


def check_row(row: Dict[str, Any]) -> List[str]:
    """Violations for one canonical ``display_ingredients`` row."""
    analysis = row.get("analysis")
    if not isinstance(analysis, dict):
        return []

    note = analysis.get("form_note")
    preview = analysis.get("form_note_preview")
    label = analysis.get("display_form_label") or row.get("display_name") or "?"
    problems = _check_form_note(note, preview, label)
    evidence = analysis.get("form_evidence")
    if evidence is not None:
        problems.extend(
            validate_exported_form_evidence(evidence, label=f"{label}.form_evidence")
        )
    if not isinstance(note, str) or not note.strip():
        return problems

    # A note may only sit beside a rendered tier; bio_score drives that tier.
    if analysis.get("bio_score") is None:
        problems.append(f"{label}: form_note on a row with null bio_score")
    if row.get("score_included") is not True:
        problems.append(f"{label}: form_note without score_included=true")
    return problems


def check_legacy_ingredient(ingredient: Dict[str, Any]) -> List[str]:
    """Validate copied form-note fields on the legacy ingredient array."""
    label = ingredient.get("display_label") or ingredient.get("name") or "?"
    problems = _check_form_note(
        ingredient.get("form_note"), ingredient.get("form_note_preview"), label
    )
    evidence = ingredient.get("form_evidence")
    if evidence is not None:
        problems.extend(
            validate_exported_form_evidence(evidence, label=f"{label}.form_evidence")
        )
    return problems


def scan(blobs_dir: Path, limit: int | None) -> Tuple[int, int, List[str]]:
    """``(blobs_scanned, notes_seen, violations)``."""
    paths = sorted(blobs_dir.glob("*.json"))
    if limit:
        paths = paths[:limit]

    notes = 0
    violations: List[str] = []
    for path in paths:
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{path.name}: unreadable ({exc})")
            continue
        for row in blob.get("display_ingredients") or []:
            if not isinstance(row, dict):
                continue
            analysis = row.get("analysis")
            if isinstance(analysis, dict) and analysis.get("form_note") is not None:
                notes += 1
            violations.extend(
                f"{path.name} :: {problem}" for problem in check_row(row)
            )
        for ingredient in blob.get("ingredients") or []:
            if not isinstance(ingredient, dict):
                continue
            if ingredient.get("form_note") is not None:
                notes += 1
            violations.extend(
                f"{path.name} :: {problem}"
                for problem in check_legacy_ingredient(ingredient)
            )
    return len(paths), notes, violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blobs-dir", type=Path, default=DEFAULT_BLOBS_DIR)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not args.blobs_dir.is_dir():
        print(f"FAIL: blobs dir not found: {args.blobs_dir}", file=sys.stderr)
        return 2

    scanned, notes, violations = scan(args.blobs_dir, args.limit)
    print(f"scanned {scanned} blobs; {notes} rows carry a form_note")

    if violations:
        print(f"\nFAIL: {len(violations)} violation(s):", file=sys.stderr)
        for violation in violations[:50]:
            print(f"  {violation}", file=sys.stderr)
        if len(violations) > 50:
            print(f"  ... and {len(violations) - 50} more", file=sys.stderr)
        return 1

    print("PASS: no form_note violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
