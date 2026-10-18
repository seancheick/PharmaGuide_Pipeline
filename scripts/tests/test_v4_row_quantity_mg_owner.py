"""One row mass-in-mg reader for the category modules.

joint_support._row_quantity_mg and sleep_support._row_quantity_mg were 31
identical lines (architecture audit 2026-10-17, AUDIT.md D.1, R6). The one copy
lives in scoring_v4.modules.generic_helpers beside has_usable_individual_dose,
which it gates on; both modules use that function object.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules import generic_helpers, joint_support, sleep_support


@pytest.mark.parametrize("row, mg", [
    ({"quantity": 500, "unit": "mg"}, 500.0),
    ({"quantity": 500, "unit": "Milligram(s)"}, 500.0),
    ({"quantity": 1.5, "unit": "g"}, 1500.0),
    ({"quantity": 2, "unit": "Gram(s)"}, 2000.0),
    ({"quantity": 300, "unit": "mcg"}, 0.3),
    ({"quantity": 300, "unit": "ug"}, 0.3),
    ({"quantity": 300, "unit": "micro grams"}, 0.3),
    ({"quantity": 3, "unit_normalized": "g", "unit": "mg"}, 3000.0),
    ({"quantity": "250", "unit": "mg"}, 250.0),
    ({"quantity": 400, "unit": "IU"}, None),
    ({"quantity": 5, "unit": "billion CFU"}, None),
    ({"quantity": 0, "unit": "mg"}, None),
    ({"quantity": -5, "unit": "mg"}, None),
    ({"quantity": None, "unit": "mg", "has_dose": True}, None),
    ({"quantity": 100, "unit": "tablet"}, None),
    ({"quantity": 500, "unit": "mg", "is_blend_header": True}, None),
    ({"quantity": 500, "unit": "mg", "blend_total_weight_only": True}, None),
])
def test_row_quantity_mg_converts_only_usable_mass(row, mg):
    assert generic_helpers._row_quantity_mg(row) == mg


@pytest.mark.parametrize("module", [joint_support, sleep_support])
def test_category_modules_use_the_one_reader(module):
    assert module._row_quantity_mg is generic_helpers._row_quantity_mg
