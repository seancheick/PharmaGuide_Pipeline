"""Gold recall/regulatory benchmark (roadmap 1.10): raw labels through the whole pipeline.

Banned or recalled products must ship BLOCKED with their rule; cautions must state the signal
that drives them; look-alike controls must not be blocked.
"""

import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.scored_artifact import build_scored_artifact

SCRIPTS = Path(__file__).resolve().parents[1]
DOC = json.loads((SCRIPTS / "tests" / "fixtures" / "safety_regulatory_gold_cases.json").read_text())
CASES = DOC["cases"]


@pytest.fixture(scope="module")
def pipeline():
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def test_fixture_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    assert DOC["_metadata"]["case_count"] == len(CASES)
    assert all(str(c["raw_label"]["id"]) == c["dsld_id"] for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_label_yields_expected_safety_status_and_driver(pipeline, case):
    normalizer, enricher = pipeline
    cleaned = normalizer.normalize_product(copy.deepcopy(case["raw_label"]))
    enriched, _ = enricher.enrich_product(cleaned)
    scored = build_scored_artifact(enriched)
    expect = case["expect"]
    assert scored["product_safety_status"] == expect["product_safety_status"]
    driver = expect["driver"]
    if expect["product_safety_status"] == "blocked":
        assert (scored.get("safety_decision") or {}).get("winning_rule") == driver
    elif driver is None:
        assert scored["safety_signal_reason"] is None
    else:
        assert (scored["safety_signal_reason"] or "").startswith(driver)
