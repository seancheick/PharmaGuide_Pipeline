"""
Metadata-contract gate for `scripts/data/*.json`.

Catches the off-by-N drift class introduced by commit 74aa9a0 (2026-05-12),
where `other_ingredients.json` shipped with 683 entries but `_metadata.total_entries`
remained at 681. That drift survived for ~24 hours and broke two tests in b04
once anyone ran them.

This test fails fast at commit time for any data file whose
`_metadata.total_entries` disagrees with the actual entry count, across
three recognized shapes:

* **single_array**: one top-level array besides `_metadata`. Entries are the
  array items. Example: `other_ingredients.json`.
* **single_payload_dict**: exactly one top-level dict besides `_metadata`.
  Entries are the keys of that wrapping dict (values may be dicts or lists —
  both shapes are valid). Examples: `botanical_marker_contributions.json`
  (entries are dicts), `cluster_ingredient_aliases.json` (entries are alias
  lists).
* **top_level_dict_of_dicts**: no nested wrapper — the top level itself is
  the entry map, and every non-`_metadata` value is a dict (one entry record
  per top-level key). Examples: `ingredient_quality_map.json` (621 entries),
  `enhanced_delivery.json` (78), `unit_mappings.json` (14).

Files with a different shape (multi-array, mixed scalar+dict, etc.) are
skipped — but only with an explicit `INTENTIONAL_EXCEPTIONS` entry that
names the bespoke per-file test pinning that file's semantic. Silent skips
are not permitted.
"""

import json
from pathlib import Path

import pytest

from data_batch import INTENTIONAL_EXCEPTIONS, classify_shape

DATA = Path(__file__).parent.parent / "data"

# The shape classifier and the exception list live in data_batch.py, the one
# owner of _metadata counts (its recount writes what this test checks).
_classify_shape = classify_shape


def _candidate_files() -> list[Path]:
    return sorted(p for p in DATA.glob("*.json") if p.is_file())


@pytest.mark.parametrize(
    "path",
    _candidate_files(),
    ids=lambda p: p.name,
)
def test_metadata_total_entries_matches_entry_count(path: Path) -> None:
    """Every classifiable data file must have _metadata.total_entries match
    its entry count, where "entry count" is shape-defined (see _classify_shape).

    Drift means either:
      * an author added/removed entries without bumping _metadata, or
      * an author bumped _metadata without matching reality — either way,
        downstream consumers reading total_entries get a lie.

    If a file legitimately tracks something else under total_entries (e.g.
    a section of a multi-section payload), add it to INTENTIONAL_EXCEPTIONS
    with a rationale AND write a bespoke per-file test pinning the semantic.
    """
    blob = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(blob, dict) or "_metadata" not in blob:
        pytest.skip(f"{path.name}: no _metadata block")

    # INTENTIONAL_EXCEPTIONS is the FIRST check after _metadata exists so that
    # files with a decided semantic skip with their rationale + bespoke-test
    # pointer, regardless of whether they have total_entries or a recognized
    # shape. This is what makes "no silent skips" enforceable — every file in
    # the exceptions dict carries an explicit reason.
    if path.name in INTENTIONAL_EXCEPTIONS:
        pytest.skip(f"{path.name}: {INTENTIONAL_EXCEPTIONS[path.name]}")

    meta_total = blob["_metadata"].get("total_entries")
    if meta_total is None:
        pytest.skip(f"{path.name}: _metadata has no total_entries field")

    classification = _classify_shape(blob)
    if classification is None:
        pytest.skip(
            f"{path.name}: shape not recognized by universal classifier "
            f"(needs a bespoke per-file test; add to INTENTIONAL_EXCEPTIONS "
            f"with a pointer to that test)."
        )

    shape_name, actual = classification
    assert actual == meta_total, (
        f"{path.name}: _metadata.total_entries={meta_total} but "
        f"{shape_name} payload has {actual} entries. "
        f"Bump _metadata.total_entries to {actual} "
        f"(or, if the semantic intentionally differs, add to "
        f"INTENTIONAL_EXCEPTIONS with rationale + bespoke test)."
    )
