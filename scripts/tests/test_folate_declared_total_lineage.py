"""Regression: a label-declared folate DFE total owns its form conversion.

O.N.E. declares one folate dose as ``667 mcg DFE (400 mcg L-5-MTHF)``.
The form amount is useful label context, but its independently derived
``680 mcg DFE`` must not become a second stack dose.
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


def test_declared_folate_dfe_total_marks_matching_mthf_conversion_as_component(
    enricher: SupplementEnricherV3,
) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [
                {
                    "name": "Folate",
                    "standardName": "Folate",
                    "canonical_id": "vitamin_b9_folate",
                    "quantity": 667,
                    "unit": "mcg DFE",
                    "dailyValue": 167,
                },
                {
                    "name": "L-5-MTHF",
                    "standardName": "Folate",
                    "canonical_id": "vitamin_b9_folate",
                    "quantity": 400,
                    "unit": "mcg",
                    "dailyValue": 167,
                },
            ],
            "inactiveIngredients": [],
        },
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    rows = result["analyzed_ingredients"]
    declared = next(row for row in rows if row["ingredient"] == "Folate")
    component = next(row for row in rows if row["ingredient"] == "L-5-MTHF")

    assert declared["dose_role"] == "declared_total"
    assert declared["source_label_key"]
    assert declared["parent_label_key"] is None
    assert declared["per_day_max"] == pytest.approx(667)

    assert component["dose_role"] == "form_component"
    assert component["parent_label_key"] == declared["source_label_key"]
    assert component["skip_ul_check"] is True
    assert component["skip_ul_reason"] == "form_component_of_declared_total"
    assert result["reference_data_version"] == "5.0.0-2026-06-28"
    assert result["reference_data_fingerprint"].startswith("sha256:")
