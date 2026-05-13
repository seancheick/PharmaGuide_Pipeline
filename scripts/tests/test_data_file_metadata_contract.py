"""
Metadata-contract gate for `scripts/data/*.json`.

Catches the off-by-N drift class introduced by commit 74aa9a0 (2026-05-12),
where `other_ingredients.json` shipped with 683 entries but `_metadata.total_entries`
remained at 681. That drift survived for ~24 hours and broke two tests in b04
once anyone ran them.

This test fails fast at commit time for any single-array data file whose
`_metadata.total_entries` disagrees with the actual array length.

Scope: only files with the simple shape `{"_metadata": {...}, "<key>": [...]}`.
Multi-array files (e.g. clinical_risk_taxonomy.json), dict-keyed files
(e.g. ingredient_quality_map.json), and files without `total_entries`
(e.g. fda_unii_cache.json) are skipped — those have their own per-file tests.
"""

import json
from pathlib import Path

import pytest

DATA = Path(__file__).parent.parent / "data"

# Files whose top-level array length intentionally does not equal
# _metadata.total_entries (e.g. count tracks something else). Add with reason.
INTENTIONAL_EXCEPTIONS: dict[str, str] = {}


def _candidate_files() -> list[Path]:
    return sorted(p for p in DATA.glob("*.json") if p.is_file())


@pytest.mark.parametrize(
    "path",
    _candidate_files(),
    ids=lambda p: p.name,
)
def test_metadata_total_entries_matches_array_length(path: Path) -> None:
    """Every single-array data file must have _metadata.total_entries == len(array).

    Drift means either:
      * an author added/removed entries without bumping _metadata, or
      * an author bumped _metadata without matching the array — either way,
        downstream consumers reading total_entries get a lie.

    If a file legitimately tracks something else under total_entries, add it
    to INTENTIONAL_EXCEPTIONS with a comment explaining the semantic.
    """
    blob = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(blob, dict) or "_metadata" not in blob:
        pytest.skip(f"{path.name}: no _metadata block")

    meta_total = blob["_metadata"].get("total_entries")
    if meta_total is None:
        pytest.skip(f"{path.name}: _metadata has no total_entries field")

    top_level_arrays = [(k, v) for k, v in blob.items() if isinstance(v, list)]
    if len(top_level_arrays) != 1:
        pytest.skip(
            f"{path.name}: has {len(top_level_arrays)} top-level arrays "
            f"(needs file-specific test, not this universal contract)"
        )

    if path.name in INTENTIONAL_EXCEPTIONS:
        pytest.skip(f"{path.name}: {INTENTIONAL_EXCEPTIONS[path.name]}")

    array_key, array_val = top_level_arrays[0]
    actual = len(array_val)
    assert actual == meta_total, (
        f"{path.name}: _metadata.total_entries={meta_total} but array "
        f"{array_key!r} has {actual} entries. "
        f"Bump _metadata.total_entries to {actual} "
        f"(or add to INTENTIONAL_EXCEPTIONS with rationale)."
    )
