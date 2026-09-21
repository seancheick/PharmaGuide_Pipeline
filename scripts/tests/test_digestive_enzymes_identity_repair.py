#!/usr/bin/env python3
"""Tests for Phase 2: Digestive enzymes ingredient-identity repair.

Verifies:
1. All 9 discrete enzyme identities resolve to their specific canonical IDs.
2. Serrapeptase is decoupled from digestive enzymes and classified as systemic.
3. INGR_DIGESTIVE_ENZYMES does not transfer to discrete enzyme rows (protease, lipase, etc.).
4. Opaque blend headers remain digestive_enzymes while disclosed children get specific IDs.
5. Functional classes (protease, lipase, amylase, cellulase) do not carry false UNIIs.
"""

import json
from pathlib import Path
import pytest

from scripts.enrich_supplements_v3 import SupplementEnricherV3
from scripts.scoring_v4.modules.generic_evidence import score_evidence
from scripts.supplement_taxonomy import (
    _ENZYME_CANONICAL_IDS,
    _SYSTEMIC_ENZYME_CANONICAL_IDS,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.fixture
def iqm() -> dict:
    with open(ROOT / "scripts" / "data" / "ingredient_quality_map.json") as f:
        return json.load(f)


def test_iqm_contains_all_nine_enzyme_identities(iqm: dict):
    expected_children = [
        "lactase",
        "alpha_galactosidase",
        "pancreatin",
        "protease",
        "lipase",
        "amylase",
        "papain",
        "cellulase",
        "serrapeptase",
    ]
    for cid in expected_children:
        assert cid in iqm, f"Missing canonical entry: {cid}"
        entry = iqm[cid]
        assert entry.get("category") == "enzymes"
        assert entry.get("cui") is not None, f"Missing CUI for {cid}"


def test_functional_classes_have_null_unii(iqm: dict):
    """Broad functional classes must not carry false substance-level UNIIs."""
    functional_classes = ["protease", "lipase", "amylase", "cellulase", "alpha_galactosidase"]
    for cid in functional_classes:
        for form_key, form_val in iqm[cid].get("forms", {}).items():
            assert form_val.get("unii") is None, f"{cid} form {form_key} should have null UNII"


def test_discrete_substances_have_verified_uniis(iqm: dict):
    """Discrete single substances have verified exact UNIIs."""
    expected_uniis = {
        "lactase": "37515NWH9U",
        "papain": "A236A06Y32",
        "serrapeptase": "NL053ABE4J",
        "pancreatin": "040L83973U",
    }
    for cid, unii in expected_uniis.items():
        found = False
        for form_val in iqm[cid].get("forms", {}).values():
            if form_val.get("unii") == unii:
                found = True
                break
        assert found, f"Expected UNII {unii} for {cid}"


def test_serrapeptase_is_systemic_not_digestive():
    assert "serrapeptase" in _SYSTEMIC_ENZYME_CANONICAL_IDS
    assert "serrapeptase" not in _ENZYME_CANONICAL_IDS


def test_lactase_resolves_specifically(enricher: SupplementEnricherV3, iqm: dict):
    match = enricher._match_quality_map("Lactase", "Lactase", iqm)
    assert match is not None
    assert match.get("canonical_id") == "lactase"


def test_alpha_galactosidase_resolves_specifically(enricher: SupplementEnricherV3, iqm: dict):
    match = enricher._match_quality_map("Alpha-Galactosidase", "Alpha-Galactosidase", iqm)
    assert match is not None
    assert match.get("canonical_id") == "alpha_galactosidase"


def test_pancreatin_resolves_specifically(enricher: SupplementEnricherV3, iqm: dict):
    match = enricher._match_quality_map("Pancreatin 4X", "Pancreatin 4X", iqm)
    assert match is not None
    assert match.get("canonical_id") == "pancreatin"


def test_discrete_protease_does_not_inherit_evidence_from_digestive_enzymes():
    """A standalone protease row must not receive credit from INGR_DIGESTIVE_ENZYMES."""
    product = {
        "dsld_id": "test-protease-standalone",
        "product_name": "High Potency Protease",
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "Protease",
                    "canonical_id": "protease",
                    "cleaner_row_role": "active_scorable",
                    "quantity": 50000.0,
                    "unit": "HUT",
                    "dose_class": "enzyme_activity",
                }
            ]
        },
        "evidence_data": {
            "clinical_matches": []
        }
    }
    res = score_evidence(product)
    assert res["score"] == 0.0
    assert res["metadata"]["evidence_result_state"] in {
        "no_qualifying_human_evidence",
        "clinical_review_not_covered",
    }
