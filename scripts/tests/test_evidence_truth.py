"""Missing research, unfinished processing or bad matching never reads as a scientific zero.

A completed zero and an unresolved review stay distinct on every route, and neither
earns credit here (Sean, November 3, 2026). Every label here is a real DSLD label.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
NOT_ESTABLISHED = "has not established a match"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _enrich(pipeline, label):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    return enricher.enrich_product(normalizer.normalize_product(raw))[0]


# Open review, Evidence 0: read "not established" before this, across the routes that had it.
@pytest.mark.parametrize("label, module", [
    pytest.param("evidence_truth_231852_raw.json", "generic", id="generic_ubiquinol_contexts_missing"),
    pytest.param("evidence_truth_252423_raw.json", "generic", id="generic"),
    pytest.param("evidence_truth_253729_raw.json", "fiber_digestive", id="fiber"),
    pytest.param("evidence_truth_295065_raw.json", "sports", id="sports"),
    pytest.param("evidence_truth_18174_raw.json", "probiotic", id="probiotic"),
])
def test_an_open_review_reads_as_open(pipeline, label, module):
    from assessment_readiness import evidence_review_open
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, label))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["_v4_module_breakdown"]["module"] == module
    assert scored["quality_assessment_status"] == "partial"
    assert evidence_review_open(scored["assessment_readiness"]["release_assessment"])
    assert evidence["score"] == 0
    assert evidence["evidence_result_state"] in {
        "applicability_unestablished", "research_present_applicability_unestablished"}
    assert evidence["display_state"] == "not_yet_reviewed"
    assert "review pending" in evidence["reason"]
    assert NOT_ESTABLISHED not in evidence["reason"]


def test_a_finished_mismatch_keeps_its_finding(pipeline):
    """60601's signed scope excludes "cardiovascular health": finished, and it says so."""
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, "evidence_truth_60601_raw.json"))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "complete"
    assert evidence["score"] == 0
    assert evidence["display_state"] == "applicability_unestablished"
    assert NOT_ESTABLISHED in evidence["reason"]
