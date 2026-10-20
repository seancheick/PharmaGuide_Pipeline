"""A gluten-free claim is contradicted only by gluten-grain evidence.

2026-10-19: claim validation voided a gluten-free claim on ANY may-contain or
facility warning, so "Manufactured in a facility that also produces products
that contain milk" removed gluten_free_validated (the app's gluten-free badge)
from real labels: 229974 (Culturelle Probiotic + Multivitamin Gummies), 304605
(GNC 50 Plus Gummy Multivitamin), 218190 (Culturelle Baby Calm + Comfort).
Cross-contact now counts only for a gluten-containing grain (21 CFR
101.91(a)(1): wheat, rye, barley and their crossbreeds); a may-contain signal
that no parsed statement explains still voids the claim. Control: 204624
(Garden of Life Maca Root) names wheat in its facility statement.
"""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(pid):
        raw = json.loads((FIXTURES / f"gluten_claim_{pid}_raw.json").read_text(encoding="utf-8"))
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        scored = build_scored_artifact(enriched)
        validations = scored["_v4_module_breakdown"]["dimensions"]["transparency"]["metadata"]["claim_validations"]
        return enriched, validations

    return run


@pytest.mark.parametrize("pid", ["229974", "304605", "218190"])
def test_non_gluten_cross_contact_keeps_the_gluten_free_claim(pipeline, pid):
    enriched, validations = pipeline(pid)
    cross = [h for h in enriched["allergen_hits"] if h["presence_type"] in ("may_contain", "facility_warning")]
    assert cross and not any(h["allergen_id"] in ("ALLERGEN_WHEAT", "ALLERGEN_BARLEY", "ALLERGEN_RYE") for h in cross)
    assert enriched["claim_gluten_free_validated"] is True
    assert validations["gluten_free"] is True


def test_wheat_facility_warning_still_voids_the_claim(pipeline):
    enriched, validations = pipeline("204624")
    assert any(h["allergen_id"] == "ALLERGEN_WHEAT" and h["presence_type"] == "facility_warning"
               for h in enriched["allergen_hits"])
    assert enriched["claim_gluten_free_validated"] is False
    assert validations["gluten_free"] is False


def _hit(allergen_id, presence):
    return {"allergen_id": allergen_id, "presence_type": presence}


@pytest.mark.parametrize("hits,unread,conflicts,expected", [
    ([_hit("ALLERGEN_MILK", "facility_warning")], False, [], False),
    ([_hit("ALLERGEN_BARLEY", "may_contain")], False, [], True),
    ([_hit("ALLERGEN_RYE", "facility_warning"), _hit("ALLERGEN_MILK", "facility_warning")], False, [], True),
    ([_hit("ALLERGEN_OATS", "may_contain")], False, [], False),  # oats are not a 101.91 gluten grain
    ([], True, [], True),  # "may contain" text no parsed statement explains
    ([_hit("ALLERGEN_WHEAT", "contains")], False, ["gluten-free claim conflicts with detected gluten/wheat"], True),
    ([], False, [], False),
])
def test_gluten_cross_contact_rule(hits, unread, conflicts, expected):
    from scoring_input_contract import gluten_free_claim_contradicted
    assert gluten_free_claim_contradicted(hits, conflicts, unparsed_may_contain=unread) is expected


def test_a_parsed_warning_does_not_explain_a_separate_unparsed_one(pipeline):
    # Review of #187: a parsed milk facility warning must not clear the
    # contradiction from another "may contain" sentence no parsed hit came from.
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    raw = json.loads((FIXTURES / "gluten_claim_304605_raw.json").read_text(encoding="utf-8"))
    raw["statements"] = list(raw.get("statements") or []) + [
        {"type": "Precautions", "notes": "May contain traces of grain products."}
    ]
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert enriched["claim_gluten_free_validated"] is False


def test_unparsed_may_contain_flag_keeps_the_contradiction():
    from scoring_input_contract import gluten_free_claim_contradicted
    milk = [{"allergen_id": "ALLERGEN_MILK", "presence_type": "facility_warning"}]
    assert gluten_free_claim_contradicted(milk, [], unparsed_may_contain=True) is True
    assert gluten_free_claim_contradicted(milk, [], unparsed_may_contain=False) is False


def test_a_parsed_sentence_merged_into_another_hit_is_not_unparsed():
    # 204521: "May contain traces of soy due to agriculture practices." is
    # parsed (soy) even when the kept soy hit carries another statement's text.
    from enrich_supplements_v3 import SupplementEnricherV3
    product = {"statements": [
        {"notes": "Manufactured in a facility that also processes egg, milk, soy and tree nuts. May contain traces of soy due to agriculture practices."},
        {"notes": "CONTAINS: MILK, PEANUTS AND TREE NUTS (COCONUT AND MAY CONTAIN TRACE AMOUNTS OF ALMOND AND CASHEW)."},
    ]}
    assert SupplementEnricherV3()._has_unparsed_may_contain(product) is False


def _gluten_evidence(enriched):
    claims = enriched["compliance_data"]["evidence_based"]["allergen_free_claims"]
    return [ev for ev in claims if "gluten" in str(ev.get("dedupe_key"))]


def test_fish_facility_warning_keeps_gluten_free_claim_and_evidence(pipeline):
    # Sean's review of #187: 326701 (Gummies Calcium & Magnesium) has a fish-only
    # facility warning; both the validated claim and its evidence stay eligible.
    enriched, validations = pipeline("326701")
    assert enriched["claim_gluten_free_validated"] is True
    assert validations["gluten_free"] is True
    evidence = _gluten_evidence(enriched)
    assert evidence and all(ev["score_eligible"] for ev in evidence)


def test_wheat_facility_warning_marks_gluten_evidence_as_cross_contact(pipeline):
    # A gluten-grain facility statement is cross-contact, not a gluten ingredient.
    enriched, _ = pipeline("204624")
    evidence = _gluten_evidence(enriched)
    assert evidence
    assert {ev.get("ineligibility_reason") for ev in evidence} == {"may_contain_warning"}
