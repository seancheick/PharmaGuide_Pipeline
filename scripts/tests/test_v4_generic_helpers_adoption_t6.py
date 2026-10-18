"""SP-2 T6 — ADOPT-2 regression test for `generic_helpers.primary_type_of`.

T6 adds a `primary_type_of(product)` helper that reads
`supplement_taxonomy.primary_type` (canonical signal) with a fallback to
the top-level `primary_type` field. Phase 2 removes the legacy reader helper.

Contract:
  1. Prefer top-level `primary_type` field (set by enricher post-2026-05-20).
  2. Else read `supplement_taxonomy.primary_type` (nested fallback path).
  3. Else return "" — taxonomy absent (old enriched batch).

The helper is normalized lowercase / stripped.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.generic_helpers import primary_type_of


def test_top_level_primary_type_wins():
    product = {"primary_type": "omega_3"}
    assert primary_type_of(product) == "omega_3"


def test_nested_taxonomy_primary_type():
    product = {"supplement_taxonomy": {"primary_type": "multivitamin"}}
    assert primary_type_of(product) == "multivitamin"


def test_top_level_wins_over_nested():
    """If both present, top-level is canonical (enricher writes both)."""
    product = {
        "primary_type": "probiotic",
        "supplement_taxonomy": {"primary_type": "general_supplement"},
    }
    assert primary_type_of(product) == "probiotic"


def test_normalization_strips_and_lowercases():
    product = {"primary_type": "  Omega_3  "}
    assert primary_type_of(product) == "omega_3"


def test_empty_string_falls_to_nested():
    """Empty top-level primary_type should not short-circuit nested lookup."""
    product = {
        "primary_type": "",
        "supplement_taxonomy": {"primary_type": "single_vitamin"},
    }
    assert primary_type_of(product) == "single_vitamin"


def test_taxonomy_absent_returns_empty():
    """Old enriched batch with no taxonomy → empty string."""
    product = {"supplement_type": {"type": "specialty"}}
    assert primary_type_of(product) == ""


def test_none_product_is_defensive():
    assert primary_type_of(None) == ""


def test_non_dict_product_is_defensive():
    assert primary_type_of("not a dict") == ""


def test_only_unavailable_doses_require_positive_label_hidden_evidence():
    from scoring_v4.modules.generic_helpers import missing_doses_are_label_hidden

    measured = {'quantity': 1000, 'unit': 'mg'}
    hidden = {'quantity': 0, 'unit': 'NP', 'cleaner_row_role': 'nested_display_only'}
    lost = {'quantity': None, 'unit': 'mg'}
    assert missing_doses_are_label_hidden([measured, hidden])
    assert missing_doses_are_label_hidden([hidden, hidden])
    assert not missing_doses_are_label_hidden([])
    assert not missing_doses_are_label_hidden([measured])
    assert not missing_doses_are_label_hidden([measured, lost])
    assert not missing_doses_are_label_hidden([hidden, lost])
    assert not missing_doses_are_label_hidden([hidden, dict(hidden, quantity_operator='ambiguous')])


def test_a_positive_unresolved_member_prevents_hidden_group_completion():
    from scoring_v4.modules.generic_helpers import missing_doses_are_label_hidden
    assert not missing_doses_are_label_hidden([
        {'quantity': 1000, 'unit': 'mg', 'quantity_operator': 'unknown'},
        {'quantity': 0, 'unit': 'NP', 'cleaner_row_role': 'nested_display_only'},
    ])
