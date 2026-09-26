"""Which label rows show an ingredient is in the product (Sean, D1c/D1b, 2026-09-26).

One rule, used by interaction selection (enricher) and by the fingerprint the
app joins curated pairs on. A positive amount, a printed %DV above 0, a listing
inside a blend or a listing with no amount establish presence; a measured zero
("Iron 0 mg", "Vitamin D 0 mcg", "0%", "Not Present") does not. "0 NP" outside a
blend is read by category (a vitamin or mineral is a panel zero) until the
cleaner keeps a printed 0% DV apart from a missing one (register Q23).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from identity.interaction import label_row_establishes_presence  # noqa: E402


@pytest.mark.parametrize("row,present", [
    ({"quantity": 320.0, "unit": "mg"}, True),
    ({"quantity": 0.0, "unit": "NP", "cleaner_row_role": "daily_value_no_amount"}, True),
    ({"quantity": 0.0, "unit": "unspecified"}, True),
    ({"quantity": None, "unit": ""}, True),
    ({"quantity": 0.0, "unit": "NP", "raw_source_path": "ingredientRows[2].nestedRows[1]"}, True),
    ({"quantity": 0.0, "unit": "mg"}, False),
    ({"quantity": 0.0, "unit": "mcg"}, False),
    ({"quantity": 0.0, "unit": "%"}, False),
    ({"quantity": 0.0, "unit": "Not Present"}, False),
    ({"quantity": 0.0, "unit": "NP", "category": "vitamins"}, False),
    ({"quantity": 0.0, "unit": "NP", "category": "fatty_acids"}, True),
])
def test_presence_rule(row, present):
    assert label_row_establishes_presence(row) is present


def test_fingerprint_drops_measured_zeros_and_keeps_every_present_identity():
    from build_final_db import generate_ingredient_fingerprint

    enriched = {"ingredient_quality_data": {"ingredients": [
        {"canonical_id": "iron", "standard_name": "Iron", "category": "minerals", "quantity": 0.0, "unit": "mg"},
        {"canonical_id": "vitamin_d", "standard_name": "Vitamin D", "category": "vitamins", "quantity": 0.0, "unit": "mcg"},
        {"canonical_id": "magnesium", "standard_name": "Magnesium", "category": "minerals", "quantity": 100.0, "unit": "mg"},
        {"canonical_id": "cranberry", "standard_name": "Cranberry", "category": "unknown", "quantity": 0.0, "unit": "NP",
         "raw_source_path": "ingredientRows[3].nestedRows[0]", "cleaner_row_role": "nested_display_only"},
        {"canonical_id": "coq10", "standard_name": "CoQ10", "category": "enzymes", "quantity": 0.0, "unit": "unspecified"},
        {"canonical_id": "garlic_bulb", "standard_name": "Garlic Bulb", "category": "botanical", "quantity": 320.0, "unit": "mg"},
    ]}}
    fp = generate_ingredient_fingerprint(enriched)
    assert set(fp["nutrients"]) == {"magnesium"}
    assert {"cranberry", "coq10", "garlic_bulb", "garlic"} <= set(fp["herbs"])
    assert "iron" not in fp["herbs"] and "vitamin_d" not in fp["herbs"]
