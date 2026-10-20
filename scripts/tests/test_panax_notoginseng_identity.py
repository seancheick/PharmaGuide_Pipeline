"""Panax notoginseng is its own plant, not Panax ginseng.

The Seneactiv/Senactiv spellings and the source names "Panax notoginseng" and "Rosa roxburghii"
were aliases of IQM ginseng "ginseng (unspecified)", so 295773's Seneactiv (Panax notoginseng +
Rosa roxburghii) carried the Panax ginseng rule. Senactiv is a branded complex
(other_ingredients NHA_SENACTIV); a printed Panax notoginseng row is botanical panax_notoginseng
(GSRS GQX1C1175U) and meets only its own sourced advisory.
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
RULE_ID = "RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET"


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(raw: dict) -> dict:
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return enriched

    return run


def _fixture(dsld_id: int) -> dict:
    return json.loads((FIXTURES / f"notoginseng_{dsld_id}_raw.json").read_text())


def _rule_ids(enriched: dict) -> set:
    rows = enriched["ingredient_quality_data"]
    return {
        hit.get("rule_id")
        for row in rows.get("ingredients", []) + rows.get("ingredients_skipped", [])
        for hit in row.get("safety_hits") or []
    }


def _rows(enriched: dict, label: str) -> list:
    rows = enriched["ingredient_quality_data"]
    return [
        row for row in rows.get("ingredients", []) + rows.get("ingredients_skipped", [])
        if row.get("raw_source_text") == label
    ]


@pytest.mark.parametrize("dsld_id,label", [(295773, "Seneactiv"), (309960, "Senactiv")])
def test_senactiv_is_not_panax_ginseng(enrich, dsld_id, label):
    enriched = enrich(_fixture(dsld_id))
    rows = _rows(enriched, label)
    assert rows
    assert all(row.get("canonical_id") != "ginseng" for row in rows)
    assert "RULE_INGREDIENT_GINSENG" not in _rule_ids(enriched)


def test_printed_notoginseng_row_meets_its_own_advisory(enrich):
    raw = _fixture(295773)
    raw["ingredientRows"] = [{
        "order": 1, "ingredientId": 64344, "description": "", "notes": "",
        "quantity": [{
            "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "quantity": 250,
            "unit": "mg", "dailyValueTargetGroup": [], "servingSizeUnit": "Capsule(s)",
        }],
        "nestedRows": [], "name": "Panax notoginseng root extract", "category": "botanical",
        "ingredientGroup": "San-Qi Ginseng", "uniiCode": None, "alternateNames": [], "forms": [],
    }]
    enriched = enrich(raw)
    rows = _rows(enriched, "Panax notoginseng root extract")
    assert rows and {row.get("canonical_id") for row in rows} == {"panax_notoginseng"}
    rule_ids = _rule_ids(enriched)
    assert RULE_ID in rule_ids
    assert "RULE_INGREDIENT_GINSENG" not in rule_ids


SENACTIV_RULE_ID = "RULE_OTHER_SENACTIV_ANTIPLATELET"


@pytest.mark.parametrize("rule_id,subject", [
    (RULE_ID, {"db": "botanical_ingredients", "canonical_id": "panax_notoginseng"}),
    (SENACTIV_RULE_ID, {"db": "other_ingredients", "canonical_id": "NHA_SENACTIV"}),
])
def test_notoginseng_advisory_is_qualified(rule_id, subject):
    rules = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())
    rule = {r["id"]: r for r in rules["interaction_rules"]}[rule_id]
    assert rule["subject_ref"] == subject
    assert [r["drug_class_id"] for r in rule["drug_class_rules"]] == ["antiplatelets"]
    assert sorted(r["condition_id"] for r in rule["condition_rules"]) == ["bleeding_disorders", "surgery_scheduled"]
    assert rule["dose_thresholds"] == []
    for sub in rule["drug_class_rules"] + rule["condition_rules"]:
        assert sub["severity"] == "monitor" and sub["materiality"] == "presence"
        assert "https://pubmed.ncbi.nlm.nih.gov/33370633/" in sub["sources"]
        text = " ".join(str(sub[k]) for k in ("mechanism", "action", "alert_body", "informational_note"))
        assert "not established" in text
        for claim in ("stop", "dose reduction", "INR", "warfarin"):
            assert claim.lower() not in sub["alert_body"].lower()


def test_seneactiv_row_meets_the_notoginseng_advisory(enrich):
    """295773: Senactiv is Panax notoginseng (+ Rosa roxburghii) saponins, the
    material of PMID 33370633."""
    enriched = enrich(_fixture(295773))
    rows = _rows(enriched, "Seneactiv")
    assert rows and {r["canonical_id"] for r in rows} == {"NHA_SENACTIV"}
    assert SENACTIV_RULE_ID in _rule_ids(enriched)


@pytest.mark.parametrize("drug_classes,fires", [
    ([], False),
    (["anticoagulants"], False),
    (["antiplatelets"], True),
])
def test_notoginseng_advisory_reaches_only_antiplatelet_users(drug_classes, fires):
    from profile_gate_evaluator import evaluate_profile_gate

    rules = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())
    sub = {r["id"]: r for r in rules["interaction_rules"]}[RULE_ID]["drug_class_rules"][0]
    result = evaluate_profile_gate(
        sub["profile_gate"],
        {"conditions": [], "drug_classes": drug_classes, "profile_flags": []},
        {},
        base_severity=sub["severity"],
    )
    assert result.fires is fires
