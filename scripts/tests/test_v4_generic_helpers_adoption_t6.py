"""SP-2 T6 — ADOPT-2 regression test for `generic_helpers.primary_type_of`.

T6 adds a `primary_type_of(product)` helper that reads
`supplement_taxonomy.primary_type` (canonical signal) with a fallback to
the top-level `primary_type` field. The existing `supp_type_of()` helper
is left intact — this is additive, callers migrate progressively.

Contract:
  1. Prefer top-level `primary_type` field (set by enricher post-2026-05-20).
  2. Else read `supplement_taxonomy.primary_type` (nested fallback path).
  3. Else return "" — taxonomy absent (old enriched batch).

The helper is normalized lowercase / stripped, like `supp_type_of`.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.generic_helpers import primary_type_of, supp_type_of


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


# --- Co-existence with supp_type_of ---

def test_supp_type_of_still_works():
    """T6 is additive — supp_type_of must remain functional for callers
    that haven't migrated yet."""
    product = {"supplement_type": {"type": "multivitamin"}}
    assert supp_type_of(product) == "multivitamin"


def test_supp_type_of_and_primary_type_of_can_disagree():
    """Documented co-existence: legacy supp_type may say one thing,
    taxonomy primary_type may say another. Both helpers return their
    respective signal; caller decides precedence."""
    product = {
        "primary_type": "general_supplement",
        "supplement_type": {"type": "multivitamin"},  # legacy mis-classification
    }
    assert primary_type_of(product) == "general_supplement"
    assert supp_type_of(product) == "multivitamin"
