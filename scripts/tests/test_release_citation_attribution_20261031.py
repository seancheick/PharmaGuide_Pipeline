"""Source-bound checks for the citation failures found by the release gate."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"


def load(name):
    return json.loads((DATA / name).read_text())


def test_ingredient_notes_do_not_attribute_other_topics():
    iqm = load("ingredient_quality_map.json")
    for ingredient, unrelated in (
        ("methionine", "28165863"),
        ("docosapentaenoic_acid_dpa", "28165863"),
        ("tudca", "28165863"),
        ("calamari_oil", "27789370"),
        ("tuna_oil", "27789370"),
        ("st_johns_wort", "9684421"),
        ("sage", "10.1038/sj.ijo.0801322"),
    ):
        assert unrelated not in json.dumps(iqm[ingredient]), ingredient
    cherry = iqm["tart_cherry"]["forms"]["vitacherry sports extract"]["notes"]
    assert "31474096" not in cherry
    assert "40964149" in cherry


def test_hmb_letter_is_limited_to_a_reviewed_no_credit_context():
    reviews = load("backed_studies_ghost_review.json")["reviewed"]
    match = [r for r in reviews if r["entry_id"] == "INGR_HMB" and r["pmid"] == "28680453"]
    assert len(match) == 1
    assert "Discrepancies" in match[0]["live_title"]
    contexts = next(e for e in load("backed_clinical_studies.json")["backed_clinical_studies"] if e["id"] == "INGR_HMB")
    assert all(not c["scoring_eligible"] for c in contexts["study_contexts"] if "28680453" in json.dumps(c))


def test_tansy_pregnancy_source_does_not_claim_demonstrated_miscarriage():
    rules = load("ingredient_interaction_rules.json")["interaction_rules"]
    rule = next(r for r in rules if r["id"] == "RULE_BANNED_TANSY_PREGNANCY")
    pregnancy = next(c for c in rule["condition_rules"] if c["condition_id"] == "pregnancy")
    assert "Whole tansy plants can induce miscarriage" not in pregnancy["mechanism"]
    assert pregnancy["severity"] == "contraindicated"
    assert pregnancy["action"] == "Do not use in pregnancy."


def test_other_source_lists_exclude_wrong_topic_papers():
    botanicals = load("standardized_botanicals.json")["standardized_botanicals"]
    cordyceps = next(b for b in botanicals if b["id"] == "cordyceps")
    assert "20578760" not in json.dumps(cordyceps)
    additives = load("harmful_additives.json")["harmful_additives"]
    canola = next(a for a in additives if a["id"] == "ADD_CANOLA_OIL")
    active_citations = {
        "references_structured": canola["references_structured"],
        "jurisdictional_statuses": canola["jurisdictional_statuses"],
        "scientific_references": canola["scientific_references"],
        "regulatory_status": canola["regulatory_status"],
    }
    assert "10.2903/j.efsa.2010.1461" not in json.dumps(active_citations)
    assert "2023/915" in json.dumps(active_citations)
    eu_status = next(s for s in canola["jurisdictional_statuses"] if s["jurisdiction"] == "EU")
    assert eu_status["status_code"] == "permitted_with_limit"


def test_repaired_notes_do_not_keep_unqualified_benefit_or_absorption_claims():
    iqm = load("ingredient_quality_map.json")
    assert "detoxification" not in iqm["methionine"]["forms"]["l-methionine"]["notes"].lower()
    dpa = iqm["docosapentaenoic_acid_dpa"]["forms"]["docosapentaenoic acid dpa (standard)"]["notes"]
    assert "antithrombotic" not in dpa.lower()
    tudca = iqm["tudca"]["forms"]["tudca (standard)"]["notes"]
    assert "well-absorbed orally" not in tudca.lower()
    assert "human oral bioavailability" in tudca.lower()
    calamari = iqm["calamari_oil"]["forms"]["calamari oil phospholipid"]["notes"]
    assert "enhanced bioavailability" not in calamari.lower()
    cordyceps = next(b for b in load("standardized_botanicals.json")["standardized_botanicals"] if b["id"] == "cordyceps")
    assert "exercise findings" not in cordyceps["bonus_rationale"]
    assert "exercise findings" not in cordyceps["notes"]
