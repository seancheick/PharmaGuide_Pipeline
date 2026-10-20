"""Algal and krill oils keep their identity and answer to the EPA/DHA oil rule.

The DSLD group "Omega-3" repaired 305211's "life'sOmega" (form: Algal Oil Concentrate) to
fish_oil, and ADR-0005's guard kept that repair because algae_oil answered no omega-3 rule: a
vegan algal product carried the fish-oil identity to keep its bleeding warnings. Sean,
2026-10-19: preserving a warning must not force an incorrect identity. The source-qualified
link is the IQM `contains` relationship (algal oil delivers DHA, PMID 17713804; krill oil
delivers EPA and DHA, PMID 26328782): an oil that contains DHA or EPA answers to the EPA/DHA
oil rule authored on fish_oil, whose consumer copy names no single source.
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
RULES = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())["interaction_rules"]


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def run(dsld_id: int) -> dict:
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"omega3_oil_family_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[dsld_id]

    return run


def test_algal_oil_keeps_its_identity_and_meets_the_epa_dha_oil_rule(enrich):
    enriched = enrich(305211)
    [row] = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("raw_source_text") == "life'sOmega"]
    assert row["canonical_id"] == "algae_oil"
    rules = {a["rule_id"] for a in enriched["interaction_profile"]["ingredient_alerts"]}
    assert "RULE_INGREDIENT_FISH_OIL" in rules


def test_epa_dha_oil_rule_copy_names_no_single_source():
    [rule] = [r for r in RULES if r["id"] == "RULE_INGREDIENT_FISH_OIL"]
    subs = rule["condition_rules"] + rule["drug_class_rules"] + [rule["pregnancy_lactation"]]
    for sub in subs:
        for field in ("alert_headline", "alert_body", "action", "informational_note", "notes"):
            assert "fish" not in str(sub.get(field) or "").lower(), (sub.get("condition_id") or sub.get("drug_class_id"), field)
