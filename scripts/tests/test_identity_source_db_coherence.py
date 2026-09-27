"""A repaired identity carries the registry that holds it.

The identity decision can replace a row's canonical_id (the DSLD group
"Cherry" turns other_ingredients "Cherry powder" into IQM dark_sweet_cherry;
"Ginger root extract" from standardized ginger_extract into IQM ginger) while
canonical_source_db kept naming the cleaner's registry. Scoring reads that
field: a ginger row repaired to IQM still counted as standardized-botanical
evidence. Sean, 2026-09-27: fix the scorable rows.
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
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize(
    "pid,canonical_id",
    [
        (64494, "dark_sweet_cherry"),  # "Cherry powder", cleaner other_ingredients
        (28986, "ginger"),  # "Ginger root extract", cleaner standardized ginger_extract
    ],
)
def test_a_scorable_repaired_row_names_the_registry_of_its_identity(enricher, normalizer, pid, canonical_id):
    from identity_integrity import canonical_registry_collections

    raw = json.loads((FIXTURES / f"stale_source_db_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    collections = canonical_registry_collections(enricher.databases)
    rows = [
        row for row in enriched["ingredient_quality_data"]["ingredients"]
        if row.get("scoreable_identity") and row.get("canonical_source_db") in collections
    ]
    assert canonical_id in {row["canonical_id"] for row in rows}
    for row in rows:
        assert row["canonical_id"] in collections[row["canonical_source_db"]], (
            row["name"], row["canonical_id"], row["canonical_source_db"],
        )
