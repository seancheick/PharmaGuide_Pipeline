"""Metadata contract for `migration_report.json`.

This is a historical migration log (NOT a runtime data file consumed by
the pipeline) — it records what changed during a specific schema migration
so future agents can trace it. The top-level shape:

* ``alias_collisions_resolved`` — PRIMARY array (38 entries) of the
  collisions this migration fixed.
* ``relationships_added`` (24), ``category_normalizations`` (6),
  ``new_fields_added`` (7) — secondary arrays of the other changes.
* ``counts`` (dict, 2 keys), ``aliases_removed`` (dict, 3 keys) —
  summary dicts.

Convention:
    ``_metadata.total_entries`` tracks ``len(alias_collisions_resolved)``
    only — the headline number for this migration. The other arrays/dicts
    are scaffolding describing the migration's secondary effects.

If you re-run the migration and the headline collision count changes,
bump ``total_entries`` to match. Adding to secondary arrays does NOT
change ``total_entries``.

NOTE: this file is essentially append-only audit history. Once a
migration ships, this file's contents are immutable. If a new migration
runs, it should produce a NEW migration_report file (e.g.
``migration_report_<date>.json``), not overwrite this one.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "migration_report.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_alias_collisions_resolved_only(blob):
    expected = len(blob["alias_collisions_resolved"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but alias_collisions_resolved "
        f"has {expected} entries. Bump total_entries to {expected}."
    )
