"""Clinical lock for the NIH/FNB supplemental-niacin UL form scope."""

from __future__ import annotations

import json
from pathlib import Path


DATA_PATH = Path(__file__).parent.parent / "data" / "rda_optimal_uls.json"
NASEM_SOURCE = "https://www.ncbi.nlm.nih.gov/books/NBK114304/"


def test_niacin_ul_scope_includes_supplemental_niacin_forms() -> None:
    data = json.loads(DATA_PATH.read_text())
    niacin = next(
        row
        for row in data["nutrient_recommendations"]
        if row.get("id") == "niacin"
    )

    assert niacin["ul_applies_to_forms"] == [
        "nicotinic acid",
        "nicotinamide (niacinamide)",
        "inositol hexanicotinate",
    ]
    assert niacin["ul_scope_source"] == NASEM_SOURCE
    note = niacin["ul_note"].lower()
    assert "all added or supplemental forms" in note
    assert "bioavailability adjustment" in note
