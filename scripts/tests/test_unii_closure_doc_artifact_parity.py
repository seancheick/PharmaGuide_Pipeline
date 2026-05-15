"""Governance invariant: closure-doc shipped backfills must match data file state.

This test catches the silent-failure class that produced commit 6e1dfcc:
docs/UNII_BACKFILL_DEFERRED.md claimed PII_PURIFIED_FISH_OIL had been
backfilled with UNII XGF7L72M0F, but the commit only modified
manufacturer_violations.json — the authoritative target file
(other_ingredients.json) was never touched. The silent failure was caused
by a basename-vs-fullpath bug in apply_one_entry() in
scripts/api_audit/backfill_unii_from_cache.py (fixed in 6122655).

The fix to the apply script alone is not enough — without an artifact-
verification gate, the same class of failure (closure doc claims X, data
file does not have X) could reappear under any new bug. This test makes
it impossible to land a closure-doc claim that drifts from data-file
reality.

## Invariant

For every entry in the "What shipped (N backfills)" table of
docs/UNII_BACKFILL_DEFERRED.md, the corresponding entry in the data file
MUST carry the claimed UNII at external_ids.unii.

This is the artifact-verified contract: closure docs cannot claim shipped
backfills unless the authoritative target file in git history has the UNII.

The implication runs one way only: shipped claim ⇒ file has UNII. A UNII
present in the file but not claimed shipped (e.g. older backfills
predating the closure doc) does NOT trigger this test. Only false claims
trigger it.

## What this test does NOT cover

* "Shipped to live catalog / Supabase" — that requires a downstream
  rebuild + sync step. The invariant here is artifact-level (data file
  in git). Catalog-level deployment is a separate gate.
* Annotations / governance entries that don't claim a UNII (the vitamin_k
  cui_note row, for example, has no proposed UNII to verify).
* Deferred entries — the "Deferred — *" sections are explicitly NOT
  scanned. Deferred means "not yet applied"; absence of UNII in the file
  is the expected state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLOSURE_DOC = REPO_ROOT / "docs" / "UNII_BACKFILL_DEFERRED.md"
DATA_DIR = REPO_ROOT / "scripts" / "data"

# Map closure-doc scope prefix → (filename, list_key | None for IQM root-dict)
SCOPE_TO_FILE: dict[str, tuple[str, Optional[str]]] = {
    "iqm": ("ingredient_quality_map.json", None),
    "other": ("other_ingredients.json", "other_ingredients"),
    "botanical": ("botanical_ingredients.json", "botanical_ingredients"),
    "standardized_botanicals": ("standardized_botanicals.json", "standardized_botanicals"),
}

# Match a shipped-table row:
#   | `<scope>:<entry_id>` | `<UNII>` | <signal> |
# UNII is exactly 10 alphanumeric chars (FDA standard). entry_id allows
# any non-backtick chars to support hyphens, underscores, mixed case.
_SHIPPED_ROW_RE = re.compile(
    r"^\|\s*`([a-z_]+):([^`]+)`\s*\|\s*`([A-Z0-9]{10})`\s*\|"
)


def _read_closure_doc() -> str:
    if not CLOSURE_DOC.exists():
        pytest.skip(
            f"Closure doc {CLOSURE_DOC} not present — invariant has nothing to verify"
        )
    return CLOSURE_DOC.read_text(encoding="utf-8")


def _extract_shipped_section(text: str) -> str:
    """Pull out the body of the 'What shipped' section.

    The section header pattern in the doc is `## What shipped (N backfills)`
    or similar. We grab everything between that header and the next H2.
    """
    m = re.search(
        r"^##\s+What shipped\b[^\n]*\n(.*?)(?=^##\s)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        raise RuntimeError(
            "Closure doc structure changed: cannot locate '## What shipped' "
            "section. Update test_unii_closure_doc_artifact_parity.py to "
            "match the new structure, or restore the section."
        )
    return m.group(1)


def _parse_shipped_rows(section: str) -> list[tuple[str, str, str]]:
    """Return list of (scope, entry_id, claimed_unii) tuples from the table."""
    rows = []
    for line in section.splitlines():
        m = _SHIPPED_ROW_RE.match(line)
        if m:
            rows.append((m.group(1), m.group(2).strip(), m.group(3)))
    return rows


def _load_entry_unii(scope: str, entry_id: str) -> Optional[str]:
    """Return external_ids.unii for the named entry, or None if missing/not found."""
    if scope not in SCOPE_TO_FILE:
        raise ValueError(
            f"Unknown scope {scope!r} in closure doc. Add to SCOPE_TO_FILE if "
            f"a new reference file was introduced."
        )
    filename, list_key = SCOPE_TO_FILE[scope]
    file_path = DATA_DIR / filename
    if not file_path.exists():
        return None
    blob = json.loads(file_path.read_text(encoding="utf-8"))
    if list_key is None:
        # IQM-style: top-level dict-of-dicts at root
        entry = blob.get(entry_id)
    else:
        items = blob.get(list_key, [])
        entry = next((it for it in items if it.get("id") == entry_id), None)
    if not isinstance(entry, dict):
        return None
    ext = entry.get("external_ids") or {}
    return ext.get("unii")


# ---------------------------------------------------------------------------
# Module-level parametrize: parse the doc once at collection time. If the
# parse fails, the test below will still fail with a clear message rather
# than silently collecting zero cases.
# ---------------------------------------------------------------------------
def _collect_shipped_rows() -> list[tuple[str, str, str]]:
    try:
        text = _read_closure_doc() if CLOSURE_DOC.exists() else ""
        if not text:
            return []
        section = _extract_shipped_section(text)
        return _parse_shipped_rows(section)
    except Exception:  # pragma: no cover — re-raised in the canary test below
        return []


_SHIPPED_ROWS = _collect_shipped_rows()


def test_closure_doc_shipped_section_is_parseable():
    """Canary: the closure doc must have a parseable shipped table.

    If this fails, the structure of UNII_BACKFILL_DEFERRED.md has drifted
    from the regex this test uses. Either update the doc back to the
    documented format or update _SHIPPED_ROW_RE to match the new format.
    """
    text = _read_closure_doc()
    section = _extract_shipped_section(text)
    rows = _parse_shipped_rows(section)
    assert len(rows) > 0, (
        "Parsed zero rows from 'What shipped' section. Either the doc has "
        "no shipped backfills (unlikely) or the table format has drifted "
        "from the |scope:entry_id|UNII|signal| convention. Inspect:\n\n"
        f"{section[:500]}..."
    )


@pytest.mark.parametrize(
    ("scope", "entry_id", "claimed_unii"),
    _SHIPPED_ROWS,
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_shipped_backfill_unii_matches_data_file(
    scope: str,
    entry_id: str,
    claimed_unii: str,
) -> None:
    """Each closure-doc shipped entry must carry its claimed UNII in the data file.

    This is the artifact-parity invariant. If it fails, either:
      (a) the data backfill silently failed to apply (commit the data fix), or
      (b) the closure doc is overstating what shipped (move the entry out of
          'What shipped' into a deferred / staged section).

    The original failure mode (commit 6e1dfcc) was case (a). The script-level
    fix landed in commit 6122655; this test guarantees we catch any future
    instance of either case.
    """
    actual = _load_entry_unii(scope, entry_id)
    assert actual == claimed_unii, (
        f"\n\nGOVERNANCE INVARIANT FAILURE\n"
        f"  closure doc:  docs/UNII_BACKFILL_DEFERRED.md claims "
        f"{scope}:{entry_id} shipped with UNII {claimed_unii}\n"
        f"  data file:    {SCOPE_TO_FILE[scope][0]} carries UNII {actual!r}\n\n"
        f"Either:\n"
        f"  (a) re-apply the backfill to the data file:\n"
        f"      python3 scripts/api_audit/backfill_unii_from_cache.py "
        f"--apply --entry-ids {entry_id}\n"
        f"  (b) move {entry_id} out of 'What shipped' in the closure doc\n"
        f"      (it belongs in a deferred or staged section).\n\n"
        f"This invariant exists because of the silent failure in commit "
        f"6e1dfcc — the closure doc claimed PII_PURIFIED_FISH_OIL shipped "
        f"but the data file was never updated. Don't dismiss this assertion "
        f"casually."
    )
