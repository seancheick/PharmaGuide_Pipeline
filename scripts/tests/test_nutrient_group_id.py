#!/usr/bin/env python3
"""nutrient_group_id — DISPLAY-only form_of roll-up for the Nutrients tab.

A ``form_of`` child (vitamin_k1) must roll up to its parent (vitamin_k) for
nutrient-display grouping so Vitamin K1 + Vitamin K2 aggregate as one
"Vitamin K". Driven by the IQM ``match_rules.target_id`` redirect and source
provenance, so this stays valid whether the enricher still emits the source
canonical_id or has already routed the row to the shared parent canonical.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from build_final_db import _nutrient_group_id, load_iqm_reference_index  # noqa: E402


def setup_module(_module):
    # Ensure the IQM index is populated before the helper reads it.
    load_iqm_reference_index()


def test_vitamin_k1_rolls_up_to_vitamin_k():
    # The one entry with match_rules.target_id today.
    assert _nutrient_group_id("vitamin_k1") == "vitamin_k"


def test_parent_and_plain_nutrients_have_no_redirect():
    # Parent (no target_id) and ordinary nutrients return None → the app
    # falls back to canonical_id for grouping.
    assert _nutrient_group_id("vitamin_k") is None
    assert _nutrient_group_id("magnesium") is None
    assert _nutrient_group_id("vitamin_c") is None


def test_empty_and_unknown_are_safe():
    assert _nutrient_group_id("") is None
    assert _nutrient_group_id("not_a_real_canonical_id") is None
