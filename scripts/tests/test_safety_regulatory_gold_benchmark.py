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


def test_hidden_caffeine_mixture_never_borrows_the_whole_blend_dose(pipeline):
    normalizer, enricher = pipeline
    case = next(c for c in CASES if c['id'] == 'caffeine-hidden-mixture-remains-caution')
    enriched, _ = enricher.enrich_product(
        normalizer.normalize_product(copy.deepcopy(case['raw_label']))
    )
    scored = build_scored_artifact(enriched)
    assert scored['product_safety_status'] == 'caution'
    assert 'STIMULANT_UNDISCLOSED_BLEND' in scored['flags']
    assert 'STIMULANT_CAFFEINE_HIGH_DOSE' not in scored['flags']


def test_real_label_correction_does_not_disable_over_ul_marker_precedence(pipeline):
    normalizer, enricher = pipeline
    case = next(c for c in CASES if c["dsld_id"] == "312980")
    raw = copy.deepcopy(case["raw_label"])
    molybdenum = next(row for row in raw["ingredientRows"] if row["name"] == "Molybdenum")
    # Synthetic guard control:26mg is not the reviewed25.5mg transcription.
    # The exact source correction must not blanket-convert other amounts.
    molybdenum["quantity"][0]["quantity"] = 26
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    scored = build_scored_artifact(enriched)
    assert scored["product_safety_status"] == "caution"
    assert scored["safety_signal_reason"].startswith("DOSE_OVER_UL")
    assert "B0_RETIRED_POLICY_SIGNAL_IGNORED" in scored["flags"]
    assert "DOSE_OVER_UL_CRITICAL" in scored["flags"]
