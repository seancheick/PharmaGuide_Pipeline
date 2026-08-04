"""The immune evidence ceiling is a tunable magnitude, not a literal.

``immune_support_evidence_cap`` returned a hardcoded ``17.0`` while its sibling
``evidence_floor_cap`` sat in config at ``16.5``. The two are different controls
— one is the ceiling applied to every immune product's evidence dimension, the
other bounds the floor that lifts a well-formed immune panel — so they are not
expected to be equal, and the fix is to configure the ceiling at its current
value rather than to reconcile the numbers.

Value unchanged: this is a zero-movement refactor. The test pins both the
config value and the fact that the scorer reads it, so a future recalibration is
a config edit reviewed like any other magnitude.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.modules.immune_support import immune_support_evidence_cap

CONFIG_PATH = Path(__file__).parent.parent / "scoring_v4" / "config" / "quality_score.json"

_IMMUNE_PRODUCT = {
    "primary_type": "immune_support",
    "activeIngredients": [
        {"name": "Vitamin C", "standardName": "Vitamin C", "quantity": 500.0, "unit": "mg"},
    ],
}


def _immune_block():
    data = json.loads(CONFIG_PATH.read_text())
    return data["category_magnitudes"]["immune_support"]


def test_evidence_cap_is_configured_at_its_current_value():
    assert _immune_block()["evidence_cap"] == 17.0


def test_evidence_cap_and_floor_cap_are_distinct_controls():
    block = _immune_block()
    assert block["evidence_cap"] == 17.0
    assert block["evidence_floor_cap"] == 16.5


def test_scorer_reads_the_configured_ceiling():
    assert immune_support_evidence_cap(_IMMUNE_PRODUCT) == _immune_block()["evidence_cap"]


def test_non_immune_product_has_no_ceiling():
    assert immune_support_evidence_cap({"primary_type": "generic"}) is None
