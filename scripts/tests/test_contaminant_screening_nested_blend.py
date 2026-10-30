"""Contaminant screening must read blend children that Clean keeps nested.

Clean flattens a blend whose header group is generic ("Proprietary Blend
(Combination)") but keeps the children under ``nestedIngredients`` when the
header's ``ingredientGroup`` is its own name (DSLD does this, and so does
submission transcription). Scoring, dose, IQD and interactions already read
nested children through ``_flatten_active_ingredients_for_analysis``;
``_collect_contaminant_data`` read only top-level ``activeIngredients``, so a
nested Ephedra or Yohimbe child was never screened and the product shipped
``no_known_catalog_concern`` instead of BLOCKED.

The invariant pinned here: the same label screens alike whether Clean keeps
the blend nested or flattens it.
"""

from __future__ import annotations

import copy
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

logging.disable(logging.CRITICAL)

FLATTENED_GROUP = "Proprietary Blend (Combination)"
NESTED_GROUP = "Ultra Energy Matrix"


def _child(name: str, quantity: float, unit: str, group: str) -> dict:
    return {
        "name": name,
        "ingredientGroup": group,
        "forms": [],
        "nestedRows": [],
        "quantity": [{"quantity": quantity, "unit": unit}],
    }


CHILDREN = [
    _child("Caffeine", 200, "mg", "Caffeine"),
    _child("Ephedra", 20, "mg", "Ephedra"),
    _child("Yohimbe bark extract", 10, "mg", "Yohimbe"),
    _child("Titanium Dioxide", 5, "mg", "Titanium Dioxide"),
    _child("Soy Lecithin", 50, "mg", "Soy"),
    _child("Sodium Copper Chlorophyllin", 5, "mg", "Chlorophyllin"),
]


def _raw(group: str) -> dict:
    return {
        "id": f"nested-contaminant-{group[:6]}",
        "brandName": "Probe",
        "fullName": "Energy Support",
        "servingSizes": [
            {
                "order": 1,
                "minQuantity": 1,
                "maxQuantity": 1,
                "unit": "Capsule",
                "minDailyServings": 1,
                "maxDailyServings": 1,
            }
        ],
        "statements": [],
        "physicalState": {"name": "Capsule", "langualCodeDescription": "Capsule"},
        "ingredientRows": [
            {
                "name": "Ultra Energy Matrix",
                "order": 1,
                "ingredientGroup": group,
                "forms": [],
                "quantity": [{"quantity": 290, "unit": "mg"}],
                "nestedRows": copy.deepcopy(CHILDREN),
            }
        ],
    }


@pytest.fixture(scope="module")
def runs() -> dict:
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()
    out = {}
    for label, group in (("flattened", FLATTENED_GROUP), ("nested", NESTED_GROUP)):
        cleaned = normalizer.normalize_product(_raw(group))
        enriched = enricher.enrich_product(cleaned)[0]
        out[label] = {
            "cleaned": cleaned,
            "enriched": enriched,
            "scored": build_scored_artifact(enriched),
        }
    return out


def _banned_ids(enriched: dict) -> set:
    subs = enriched["contaminant_data"]["banned_substances"]["substances"]
    return {row["banned_id"] for row in subs}


def _harmful_ids(enriched: dict) -> set:
    rows = enriched["contaminant_data"]["harmful_additives"]["additives"]
    return {row.get("additive_id") for row in rows}


def _allergen_ids(enriched: dict) -> set:
    rows = enriched["contaminant_data"]["allergens"]["allergens"]
    return {row.get("allergen_id") for row in rows}


def test_fixture_keeps_one_variant_nested(runs) -> None:
    flat_names = [r["name"] for r in runs["flattened"]["cleaned"]["activeIngredients"]]
    nested_top = runs["nested"]["cleaned"]["activeIngredients"]
    assert "Ephedra" in flat_names
    assert [r["name"] for r in nested_top] == ["Ultra Energy Matrix"]
    assert "Ephedra" in [c["name"] for c in nested_top[0]["nestedIngredients"]]


def test_nested_banned_child_blocks_the_product(runs) -> None:
    nested = runs["nested"]
    assert {"BANNED_EPHEDRA", "RISK_YOHIMBE"} <= _banned_ids(nested["enriched"])
    assert nested["scored"]["product_safety_status"] == "blocked"
    assert nested["scored"]["verdict"] == "BLOCKED"
    reasons = {
        row.get("reason")
        for row in nested["enriched"]["contaminant_data"]["banned_substances"]["substances"]
        if row["banned_id"] == "BANNED_EPHEDRA"
    }
    assert reasons and all(reasons)


def test_nested_and_flattened_screen_alike(runs) -> None:
    flat, nested = runs["flattened"]["enriched"], runs["nested"]["enriched"]
    assert _banned_ids(nested) == _banned_ids(flat)
    assert _harmful_ids(nested) == _harmful_ids(flat)
    assert _allergen_ids(nested) == _allergen_ids(flat)
    assert "ALLERGEN_SOY" in _allergen_ids(nested)
    for key in ("product_safety_status", "verdict", "has_banned_substance"):
        assert runs["nested"]["scored"].get(key) == runs["flattened"]["scored"].get(key), key


def test_banned_flag_lands_on_the_nested_child_row(runs) -> None:
    header = runs["nested"]["enriched"]["activeIngredients"][0]
    by_name = {row["name"]: row for row in header["nestedIngredients"]}
    ephedra_flags = {f.get("entry_id") for f in by_name["Ephedra"]["safety_flags"]}
    assert "BANNED_EPHEDRA" in ephedra_flags
    assert not any(
        f.get("entry_id") == "BANNED_EPHEDRA" for f in header.get("safety_flags") or []
    )
    assert not by_name["Caffeine"].get("safety_flags")


def test_rules_on_a_nested_childs_safety_record_still_fire(runs) -> None:
    def rule_ids(label: str) -> set:
        profile = runs[label]["enriched"]["interaction_profile"]
        return {alert.get("rule_id") for alert in profile["ingredient_alerts"]}

    assert "RULE_BANNED_YOHIMBE_CONTRA" in rule_ids("nested")
    assert rule_ids("nested") == rule_ids("flattened")
