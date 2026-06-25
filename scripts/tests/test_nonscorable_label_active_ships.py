"""A real disclosed label active that is recognized-but-non-scorable (no quality
score) must still RENDER as an active row, so the product ships as opaque/POOR
instead of being silently quarantined with a 0-active blob.

Regression for the BulkSupplements single-botanical class (e.g. dsld 252355
"Galla Chinensis Extract", 280321 "Xanthan Gum", "Barley Extract", "Triphala"):
the cleaner discloses 1 real active, the enricher recognizes it but has no
quality score for it (skip_reason=recognized_non_scorable / is_additive /
no_quality_map_match / blend_header_total_weight_only), so
`ingredient_quality_data.ingredients_scorable` is an EMPTY list. That makes
`_active_export_contract` "available" but EMPTY — and the old
`_active_row_allowed_for_primary_export` then rejected the only label active,
yielding blob_actives=0 → the active-count reconciliation gate quarantined a
real, already-scored product (~581 products).

Contract: an "available" but EMPTY strict contract identifies no strict primary
active, so it provides no basis to filter — real label rows must still ship.
This matches the export-contract's stated intent (build_final_db.py:1484-1490:
opaque/unidentified actives SHIP as POOR; only NOT_SCORED quarantines).
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_final_db import _active_row_allowed_for_primary_export


def _label_active():
    # A real disclosed label row, recognized identity, no safety signal.
    return {
        "raw_source_text": "Galla chinensis extract",
        "name": "Galla chinensis extract",
        "canonical_id": "galla_chinensis",
        "raw_source_path": "ingredientRows[0]",
    }


def test_empty_available_contract_allows_real_label_active():
    # ingredients_scorable was a list (contract "available") but every disclosed
    # active was non-scorable, so the allow-sets are all empty.
    empty_contract = {
        "available": True,
        "source_paths": set(),
        "terms": set(),
        "canonical_ids": set(),
    }
    assert (
        _active_row_allowed_for_primary_export(_label_active(), empty_contract) is True
    ), "an empty strict contract must not filter out the only real label active"


def test_empty_contract_still_excludes_nested_blend_child():
    # GUARD: under an empty contract, a nested blend CHILD (raw_source_path points
    # into child_ingredients / nestedRows) must NOT surface as a top-level active —
    # it's a display-only member of a proprietary blend, not a label active.
    # (Pairs with test_build_final_db
    #  ::test_export_empty_strict_primary_contract_does_not_fallback_to_blend_children.)
    empty_contract = {
        "available": True,
        "source_paths": set(),
        "terms": set(),
        "canonical_ids": set(),
    }
    blend_child = {
        "raw_source_text": "QPower",
        "name": "QPower",
        "canonical_id": "quercetin",
        "raw_source_path": "activeIngredients[0].child_ingredients[0]",
    }
    assert (
        _active_row_allowed_for_primary_export(blend_child, empty_contract) is False
    ), "a nested blend child must not surface as a top-level active under an empty contract"


def test_nonempty_contract_still_filters_offlabel_row():
    # GUARD: a NON-empty contract must keep excluding a row that isn't in it and
    # carries no safety signal (the product_level_evidence exclusion still works).
    contract = {
        "available": True,
        "source_paths": {"ingredientRows[0]"},
        "terms": {"vitamin c"},
        "canonical_ids": {"vitamin_c"},
    }
    off_label = {
        "raw_source_text": "Supports immune health",
        "name": "Supports immune health",
        "raw_source_path": "productClaims[0]",
    }
    assert (
        _active_row_allowed_for_primary_export(off_label, contract) is False
    ), "a non-empty contract must still drop an off-label product-level row"
