"""A resolved row answers to the interaction rules of the registry that owns it.

The enricher projects a recognized botanical or other-ingredient identity onto
its row as canonical_id + canonical_source_db (garlic_bulb /
botanical_ingredients). The interaction lookup read only canonical_id and
stamped every such row as an IQM subject, so a non-scorable botanical row was
dropped as an IQM blend child and never met the rules authored on its own
registry: licorice root, ginkgo leaf, blue cohosh, rue and the other
botanical-subject rules only fired for rows that had lost their canonical_id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DATA = SCRIPTS / "data"
IQM = "ingredient_quality_map"


def _rules() -> list:
    return json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _resolved_row(canonical_id: str, source_db: str) -> dict:
    """The fields the enricher stamps on a recognized non-scorable row."""
    return {
        "name": canonical_id,
        "raw_source_text": canonical_id,
        "standard_name": canonical_id,
        "canonical_id": canonical_id,
        "canonical_id_after": canonical_id,
        "canonical_source_db": source_db,
        "recognition_source": source_db,
        "recognized_entry_id": canonical_id,
        "matched_entry_id": canonical_id,
        "recognized_non_scorable": True,
        "scoreable_identity": False,
        "quantity": 500.0,
        "unit": "mg",
        "unit_normalized": "mg",
    }


def _fired(enricher, row: dict) -> set:
    product = {
        "dsld_id": "TEST_REGISTRY_SUBJECT",
        "product_name": "test",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": [row]},
    }
    profile = enricher._collect_interaction_profile(product)
    return {alert["rule_id"] for alert in profile.get("ingredient_alerts") or []}


@pytest.mark.parametrize(
    "rule_id,canonical_id,source_db",
    [
        (rule["id"], rule["subject_ref"]["canonical_id"], rule["subject_ref"]["db"])
        for rule in _rules()
        if rule["subject_ref"]["db"] in {"botanical_ingredients", "other_ingredients"}
    ],
)
def test_rule_on_a_non_iqm_registry_reaches_a_row_resolved_to_it(
    enricher, rule_id, canonical_id, source_db
):
    assert rule_id in _fired(enricher, _resolved_row(canonical_id, source_db))


@pytest.mark.parametrize("source_db", [None, "", IQM, "standardized_botanicals", "probiotic_data"])
def test_iqm_and_unroutable_registries_keep_the_iqm_subject(enricher, source_db):
    row = {"canonical_id": "turmeric", "canonical_source_db": source_db}
    assert enricher._derive_interaction_subject_ref(row) == {"db": IQM, "canonical_id": "turmeric"}


def test_botanical_row_is_a_botanical_subject(enricher):
    row = _resolved_row("garlic_bulb", "botanical_ingredients")
    assert enricher._derive_interaction_subject_ref(row) == {
        "db": "botanical_ingredients",
        "canonical_id": "garlic_bulb",
    }
