"""
Review follow-up — unknown-form Vitamin E must fail toward safety, not the lower
synthetic factor.

`_detect_vitamin_e_form` defaulted an undetected form to SYNTHETIC (0.45 mg/IU).
At high IU that under-states the mg (natural is 0.67 mg/IU), so an over-UL dose
could be hidden. Mirror vitamin A: an undetected E form resolves to
`vitamin_e_unknown` (conversions:null → flag_for_review), and the enricher skips
the UL check (not evaluable) rather than converting at the synthetic factor.
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


def test_vitamin_e_unknown_form_is_ul_skipped_not_synthetic(enricher):
    # Bare "Vitamin E 1500 IU" — no natural/synthetic token.
    product = {
        "activeIngredients": [
            {"name": "Vitamin E", "standardName": "Vitamin E", "canonical_id": "vitamin_e",
             "canonical_source_db": "ingredient_quality_map",
             "quantity": 1500, "unit": "IU", "dailyValue": None},
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    rows = [a for a in result["adequacy_results"] if "vitamin e" in (a.get("nutrient") or "").lower()]
    assert rows, "expected a Vitamin E adequacy row"
    assert rows[0].get("skip_ul_check") is True, (
        "unknown-form Vitamin E must skip the UL check, not convert at the synthetic factor"
    )
    assert rows[0].get("skip_ul_reason") == "unknown_vitamin_form"


def test_natural_vitamin_e_still_converts(enricher):
    # A named natural form must still convert (regression guard — fix only touches
    # the unknown default).
    product = {
        "activeIngredients": [
            {"name": "Vitamin E (d-alpha-tocopherol)", "standardName": "Vitamin E",
             "canonical_id": "vitamin_e", "canonical_source_db": "ingredient_quality_map",
             "quantity": 30, "unit": "IU", "dailyValue": 100.0},
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    rows = [a for a in result["adequacy_results"] if "vitamin e" in (a.get("nutrient") or "").lower()]
    assert rows, "expected a Vitamin E adequacy row"
    assert rows[0].get("skip_ul_check") is not True, "named natural form must still be evaluated"
