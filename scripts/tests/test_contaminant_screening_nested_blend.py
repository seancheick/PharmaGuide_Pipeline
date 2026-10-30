"""Contaminant screening must read blend children that Clean keeps nested.

Clean flattens a blend whose header group is generic ("Proprietary Blend
(Combination)") but keeps the children under ``nestedIngredients`` when the
header's ``ingredientGroup`` is its own name (DSLD does this, and so does
submission transcription). Scoring, dose, IQD and interactions already read
nested children through ``scoring_input_contract.active_label_rows``;
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


def test_scorer_safety_gate_reads_nested_children(runs) -> None:
    from scoring_v4.gate_safety import (
        _iter_resolver_clean_label_hits,
        _iter_resolver_safety_hits,
    )

    def rule_ids(hits) -> set:
        return {hit.get("matched_rule_id") for hit in hits}

    flat, nested = runs["flattened"]["enriched"], runs["nested"]["enriched"]
    assert "BANNED_EPHEDRA" in rule_ids(_iter_resolver_safety_hits(nested))
    assert rule_ids(_iter_resolver_safety_hits(nested)) == rule_ids(
        _iter_resolver_safety_hits(flat)
    )
    assert "BANNED_ADD_TITANIUM_DIOXIDE" in rule_ids(_iter_resolver_clean_label_hits(nested))
    assert rule_ids(_iter_resolver_clean_label_hits(nested)) == rule_ids(
        _iter_resolver_clean_label_hits(flat)
    )


def test_export_safety_and_interaction_carriers_read_nested_children(runs) -> None:
    import build_final_db as export
    from core_export_model import PRODUCTS_CORE_COLUMNS

    def carriers(label: str) -> dict:
        enriched = copy.deepcopy(runs[label]["enriched"])
        scored = copy.deepcopy(runs[label]["scored"])
        blob = export.build_detail_blob(copy.deepcopy(enriched), copy.deepcopy(scored))
        core = dict(zip(
            PRODUCTS_CORE_COLUMNS,
            export.build_core_row(enriched, scored, "2026-10-29T00:00:00Z", detail_blob=blob),
        ))
        return {
            "banned_bridge": export._resolver_status_in(enriched, ("banned",)),
            "banned_flags": {
                flag.get("entry_id")
                for flag in export.safety_flag_status_matches(enriched, "banned", "recalled")
            },
            "tags": set(
                export.classify_product_categories(enriched, scored)["key_ingredient_tags"]
            ),
            "core_tags": core["key_ingredient_tags"],
            "search_text": core["ingredients_text"],
        }

    flat, nested = carriers("flattened"), carriers("nested")
    assert nested["banned_bridge"] is True
    assert {"ephedra", "titanium_dioxide"} <= nested["tags"]
    assert "Ephedra" in nested["search_text"]
    assert nested == flat


def test_a_repeated_parent_never_hides_a_distinct_child():
    # Team audit of #298: two representations of one source row (same path,
    # name, amount) with different children. The parent is listed once; every
    # distinct child is still in the ledger that safety screening reads.
    # The October 30 corpus census found no such record (0 of 15,437).
    from scoring_input_contract import active_label_rows

    def parent(child, index):
        return {"name": "Energy Blend", "raw_source_path": "ingredientRows[0]", "quantity": 500,
                "unit": "mg", "nestedIngredients": [
                    {"name": child, "raw_source_path": f"ingredientRows[0].nestedRows[{index}]"}]}

    rows = active_label_rows([parent("Green Tea Extract", 0), parent("Yohimbe", 1),
                              parent("Green Tea Extract", 0)])
    assert [row["name"] for row in rows] == ["Energy Blend", "Green Tea Extract", "Yohimbe"]
