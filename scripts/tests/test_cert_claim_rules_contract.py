"""Metadata contract for `cert_claim_rules.json`.

This file's shape is nested-dict (``rules.<category>.<rule_id>``), so the
universal ``test_data_file_metadata_contract`` cannot apply.

Convention:
    ``_metadata.total_entries`` tracks the count of **scorable claim rules**
    across all 6 categories under ``rules.*`` (``third_party_programs``,
    ``gmp_certifications``, ``organic_certifications``, ``allergen_free_claims``,
    ``batch_traceability``, ``quality_markers``) — EXCLUDING the ``_metadata``
    sub-key that each category carries for its own per-category config
    (``description``, ``max_programs_scored``, ``points_per_program``,
    ``max_total_points``).

So: ``total_entries = Σ category[rule_id for rule_id in category if not rule_id.startswith('_')]``.

If you add a rule, bump ``total_entries`` by 1. If you add a per-category
config field inside ``_metadata``, do not bump total_entries — bump
``schema_version`` instead.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "cert_claim_rules.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _count_real_rules(rules_dict: dict) -> int:
    """Sum the rule keys across every category, excluding per-category `_metadata`.

    A "real rule" is any key that does NOT start with an underscore. This matches
    the schema convention used elsewhere in this file (and in many of the data
    files in scripts/data/) where leading-underscore keys carry config, not entries.
    """
    return sum(
        1
        for category_rules in rules_dict.values()
        if isinstance(category_rules, dict)
        for rid in category_rules.keys()
        if not rid.startswith("_")
    )


def test_total_entries_tracks_real_rule_count_across_categories(blob):
    expected = _count_real_rules(blob["rules"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but Σ(non-_-prefixed rule keys "
        f"across rules.*)={expected}. Bump total_entries to {expected}."
    )


def test_each_category_carries_its_own_metadata_block(blob):
    """Defensive: every rule category should carry a `_metadata` sub-key with
    per-category scoring config. If one disappears, the scorer will lose its
    point caps / per-program limits."""
    missing = [
        cat for cat, items in blob["rules"].items()
        if isinstance(items, dict) and "_metadata" not in items
    ]
    assert not missing, f"categories missing _metadata block: {missing}"
