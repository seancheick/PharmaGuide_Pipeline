"""An incomplete safety assessment never ships a reassuring result.

The safety gate records whether its ingredient assessment completed
(`SafetyResult.ingredient_assessment_complete`, B3). Until 2026-09-28 nothing
read the fact: with the banned/recalled resolver unavailable, Spectravite
(12012) stayed scored, rose 73.6 -> 74.6 (the resolver's clean-label penalty
vanished) and exported `no_known_catalog_concern` (audit RR-08).

Policy: when a safety resolver failed, a hard verdict the gate did establish
(BLOCKED/UNSAFE) still ships with its reason; otherwise the score is withheld
(NOT_SCORED, `safety_assessment_incomplete`) and the consumer safety state is
`not_assessed`. The gate breakdown always carries the completeness facts.
Capture gaps stay facts: the completeness gate owns a label with no assessable
active panel (in the 2026-09-22 corpus the only gaps were 4 maltodextrin
products with no actives, withheld as intentional_non_scoreable_product).
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _enrich(pipeline, label):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return enriched


def _break_resolver(monkeypatch):
    from scoring_v4 import gate_safety

    def unavailable():
        raise RuntimeError("resolver data unavailable")

    monkeypatch.setattr(gate_safety, "_inactive_resolver", unavailable)


def test_a_complete_assessment_scores_and_exports_its_facts(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, "form_association_12012_raw.json"))
    assert scored["quality_score_status"] == "scored"
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    gate = scored["_v4_safety_gate"]
    assert gate["ingredient_assessment_complete"] is True
    assert gate["ingredient_assessment_errors"] == []


def test_an_unavailable_resolver_withholds_the_score(pipeline, monkeypatch):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "form_association_12012_raw.json")
    _break_resolver(monkeypatch)
    scored = build_scored_artifact(enriched)
    assert scored["quality_score_status"] == "not_scored"
    assert scored["quality_score_v4_100"] is None
    assert scored["score_unavailable_reason"] == "safety_assessment_incomplete"
    assert scored["product_safety_status"] == "not_assessed"
    gate = scored["_v4_safety_gate"]
    assert gate["ingredient_assessment_complete"] is False
    assert "safety_resolver_unavailable" in gate["ingredient_assessment_errors"]


def test_a_known_ban_still_ships_blocked_when_the_resolver_fails(pipeline, monkeypatch):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "designer_steroid_33360_raw.json")
    _break_resolver(monkeypatch)
    scored = build_scored_artifact(enriched)
    assert scored["verdict"] == "BLOCKED"
    assert scored["product_safety_status"] == "blocked"
    assert scored["_v4_safety_gate"]["ingredient_assessment_complete"] is False


def test_a_capture_gap_is_a_fact_not_a_withheld_score():
    from scoring_v4.gate_safety import safety_resolvers_failed

    assert not safety_resolvers_failed(["capture_unavailable:inactiveIngredients"])
    assert safety_resolvers_failed(["capture_unavailable:activeIngredients[0]",
                                    "safety_resolver_failed:activeIngredients[1]"])
    assert not safety_resolvers_failed(None)
