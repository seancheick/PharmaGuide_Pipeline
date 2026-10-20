"""Star anise carries a sourced seizure-disorder caution.

Chinese star anise (Illicium verum, botanical star_anise) is GRAS as a spice,
but it can be contaminated with or mistaken for Japanese star anise (Illicium
anisatum), whose anisatin causes seizures; dried fruits cannot be told apart by
eye. FDA advisory P03-67 (2003-09-10) linked star anise teas to about 40
illnesses including seizures; Ize-Ludlow 2004 (PMID 15492355) reported 7
infants with neurologic reactions and evidence of contamination; Shen 2012
(PMID 22484123) names anisatin as the cause. Before this rule the 10 corpus
star anise products (all BulkSupplements extract powders) had no warning.

Japanese star anise is a different species: a row naming it must never take
the GRAS star_anise identity.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
RULES = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "ingredient_interaction_rules.json").read_text()
)["interaction_rules"]
RULE_ID = "RULE_BOTAN_STAR_ANISE_SEIZURE"
FDA_ADVISORY = "https://web.archive.org/web/20050115085515/http://www.fda.gov/bbs/topics/NEWS/2003/NEW00941.html"


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def _enrich(enricher, raw):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


def _rule():
    return next(r for r in RULES if r["id"] == RULE_ID)


def test_star_anise_rule_is_a_sourced_seizure_disorder_caution():
    rule = _rule()
    assert rule["subject_ref"] == {"db": "botanical_ingredients", "canonical_id": "star_anise"}
    [sub] = rule["condition_rules"]
    assert sub["condition_id"] == "seizure_disorder"
    assert (sub["severity"], sub["evidence_level"]) == ("caution", "limited")
    assert (sub["direction"], sub["materiality"]) == ("harmful", "presence")
    assert sub["profile_gate"]["requires"]["conditions_any"] == ["seizure_disorder"]
    assert set(sub["sources"]) == {
        FDA_ADVISORY,
        "https://pubmed.ncbi.nlm.nih.gov/15492355/",
        "https://pubmed.ncbi.nlm.nih.gov/22484123/",
    }
    assert "Japanese star anise" in sub["alert_body"]
    # No interaction evidence exists for any drug class; none is claimed.
    assert rule["drug_class_rules"] == [] and rule["dose_thresholds"] == []
    # Pregnancy/breastfeeding: an honest unknown, not a sourced warning.
    assert rule["pregnancy_lactation"]["pregnancy_category"] == "no_data"


@pytest.mark.parametrize("pid, name", [
    ("252910", "Star Anise extract"),
    ("311657", "Star Anise Fruit & Seed Extract"),
    ("330859", "Star Anise Fruit Extract"),
])
def test_real_star_anise_rows_fire_the_seizure_rule(enricher, pid, name):
    raw = json.loads((FIXTURES / f"star_anise_{pid}_raw.json").read_text())
    profile = _enrich(enricher, raw)["interaction_profile"]
    alerts = [a for a in profile["ingredient_alerts"] if a["rule_id"] == RULE_ID]
    assert [a["ingredient_name"] for a in alerts] == [name]
    hits = {h["condition_id"]: h["severity"] for h in alerts[0]["condition_hits"]}
    # The pregnancy_lactation block surfaces as pregnancy/lactation hits; it stays an unknown.
    assert hits == {"seizure_disorder": "caution", "pregnancy": "no_data", "lactation": "no_data"}
    assert profile["condition_summary"]["seizure_disorder"]["rule_ids"] == [RULE_ID]


@pytest.mark.parametrize("name", ["Japanese Star Anise", "Illicium anisatum", "Shikimi"])
def test_japanese_star_anise_never_takes_the_star_anise_identity(enricher, name):
    raw = json.loads((FIXTURES / "star_anise_252910_raw.json").read_text())
    raw = copy.deepcopy(raw)
    raw["ingredientRows"][0].update(name=name, ingredientGroup=name)
    enriched = _enrich(enricher, raw)
    rows = enriched["ingredient_quality_data"]["ingredients"]
    assert all(r.get("canonical_id") != "star_anise" for r in rows)
    assert all(a["rule_id"] != RULE_ID for a in enriched["interaction_profile"]["ingredient_alerts"])


def test_star_anise_agent_review_does_not_imply_clinician_review():
    owner = _rule()["review_owner"].lower()
    assert "agent" in owner
    assert "not clinician-reviewed" in owner
    author = Path(__file__).resolve().parents[1] / "audits/interaction_rules/star_anise_2026_10/apply.py"
    assert "pharmaguide_clinical_team" not in author.read_text()
