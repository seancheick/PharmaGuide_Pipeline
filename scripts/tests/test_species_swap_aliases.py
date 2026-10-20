"""A printed wheat grass, barley grass or green bell pepper row keeps its own plant.

After ADR-0005 (#181) a DSLD group cannot replace an identity whose exact curated alias is the
printed name, but these label spellings ("Wheat Grass juice powder", "Wheatgrass Juice, Powder",
"Barley grass juice", "Green Bell Pepper powder") were not curated aliases, so the group still
swapped the plant: Triticum aestivum wheat grass to Elymus repens couch grass (12 rows), young
barley grass to unspecified barley (17), a non-pungent bell pepper to chili pepper (317964).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def run(dsld_id: int) -> dict:
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"species_swap_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[dsld_id]

    return run


@pytest.mark.parametrize("dsld_id,label,canonical_id", [
    (202705, "organic Wheat grass juice powder", "wheatgrass"),
    (289060, "Wheat Grass juice powder", "wheatgrass"),
    (309388, "Wheatgrass Juice, Powder", "wheatgrass"),
    (289060, "Barley Grass Juice, Powder", "barley_grass"),
    (297644, "Barley grass juice", "barley_grass"),
    (317964, "Green Bell Pepper powder", "green_bell_pepper"),
    # Control: already a curated alias before this batch.
    (202705, "organic Green Bell Pepper", "green_bell_pepper"),
])
def test_printed_plant_is_not_replaced_by_its_dsld_group(enrich, dsld_id, label, canonical_id):
    iqd = enrich(dsld_id)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] if r.get("raw_source_text") == label]
    assert rows and {r["canonical_id"] for r in rows} == {canonical_id}
