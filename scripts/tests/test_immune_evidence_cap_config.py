"""The immune Evidence ceiling is configured; presence-based floors are retired."""

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


def test_ingredient_presence_cannot_configure_an_evidence_floor():
    block = _immune_block()
    assert block["evidence_cap"] == 17.0
    assert "evidence_floor_cap" not in block


def test_scorer_reads_the_configured_ceiling():
    assert immune_support_evidence_cap(_IMMUNE_PRODUCT) == _immune_block()["evidence_cap"]


def test_non_immune_product_has_no_ceiling():
    assert immune_support_evidence_cap({"primary_type": "generic"}) is None
