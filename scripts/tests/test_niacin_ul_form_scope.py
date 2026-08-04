"""Clinical lock for the NIH/FNB supplemental-niacin UL form scope."""

from __future__ import annotations

import json
from pathlib import Path


DATA_PATH = Path(__file__).parent.parent / "data" / "rda_optimal_uls.json"
NIH_SOURCE = "https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/"


def test_niacin_ul_scope_includes_nicotinic_acid_and_nicotinamide() -> None:
    data = json.loads(DATA_PATH.read_text())
    niacin = next(
        row
        for row in data["nutrient_recommendations"]
        if row.get("id") == "niacin"
    )

    assert niacin["ul_applies_to_forms"] == [
        "nicotinic acid",
        "nicotinamide (niacinamide)",
    ]
    assert niacin["ul_scope_source"] == NIH_SOURCE
    note = niacin["ul_note"].lower()
    assert "both" in note
    assert "nicotinic acid" in note
    assert "nicotinamide" in note
    assert "only" not in note
