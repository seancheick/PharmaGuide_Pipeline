"""
P0-1b step 1 — `ul_gate_eligible` on rda_ul_data safety_flags.

Corpus finding (13,753 mineral rows): DSLD names mineral rows by the ELEMENT and
states the ELEMENTAL mass; `dailyValue` present ⟹ elemental (validated by %DV
reconstruction). Compound-mass rows (e.g. Magtein "2000 mg" magnesium
L-threonate) carry `dailyValue: None` and compare their COMPOUND mass to the
elemental UL — a false over-UL.

So the UL verdict gate must only fire on flags whose mass is confirmed elemental.
A safety_flag is `ul_gate_eligible` iff the source row has a `dailyValue`; else it
is excluded (reason `compound_mass_not_elemental` for compound-named rows).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _mag(active):
    return {"activeIngredients": active, "inactiveIngredients": []}


def test_compound_mass_row_flag_is_gate_ineligible(enricher):
    # Zinc Picolinate 200 mg with NO dailyValue -> compound mass; 200 vs 40 mg UL.
    product = _mag([
        {"name": "Zinc Picolinate", "standardName": "Zinc", "canonical_id": "zinc",
         "canonical_source_db": "ingredient_quality_map",
         "quantity": 200, "unit": "mg", "dailyValue": None},
    ])
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    flags = [f for f in result["safety_flags"] if "zinc" in (f.get("nutrient") or "").lower()]
    assert flags, "expected an over-UL flag for 200 mg zinc vs a 40 mg UL"
    assert flags[0].get("ul_gate_eligible") is False
    assert flags[0].get("ul_gate_ineligible_reason") == "compound_mass_not_elemental"


def test_elemental_dv_row_flag_is_gate_eligible(enricher):
    # Element-named Zinc 200 mg WITH a dailyValue -> elemental -> gate-eligible.
    product = _mag([
        {"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
         "canonical_source_db": "ingredient_quality_map",
         "quantity": 200, "unit": "mg", "dailyValue": 1818.0},
    ])
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    flags = [f for f in result["safety_flags"] if "zinc" in (f.get("nutrient") or "").lower()]
    assert flags, "expected an over-UL flag for 200 mg zinc"
    assert flags[0].get("ul_gate_eligible") is True
