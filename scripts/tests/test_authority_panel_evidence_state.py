"""Authority-panel Evidence declares the result it reached.

Multivitamin, prenatal and B-complex Evidence is scored from the essential
nutrient panel by `evidence_resolver.resolve_authority_panel_evidence` (f2efb793).
That seam returned points but no `evidence_result_state`, and the assembler shows
an undeclared state as `not_yet_reviewed`: Spectravite (12012) and Nature Made
Prenatal (180316) scored 20/20 and told the user "our review of the rest is still
open" (audit RR-11; 1,553 products in candidate 0d4d59a6).

The panel's rows are composed like any product's (`resolve_product_evidence`
precedence): an open row keeps the coverage-gap state; authority coverage is
`evaluated_authority`; zero coverage is never read as a reviewed null.
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


def _scored(pipeline, label):
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return build_scored_artifact(enriched)


@pytest.mark.parametrize("label,route", [
    ("form_association_12012_raw.json", "multi_or_prenatal"),
    ("prenatal_180316_raw.json", "multi_or_prenatal"),
    ("b_complex_19173_raw.json", "b_complex"),
])
def test_a_covered_panel_is_an_authority_result(pipeline, label, route):
    scored = _scored(pipeline, label)
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["_v4_module"] == route
    assert evidence["score"] > 0
    assert evidence["evidence_result_state"] == "evaluated_authority"
    assert evidence["display_state"] == "assessed"
    assert "still open" not in evidence["reason"]


def _panel_state(monkeypatch, dispositions, covered=(), assessable=True):
    from evidence_resolver import ProductEvidenceResolution, compose_product_resolution_state
    from scoring_v4.modules import generic_evidence

    monkeypatch.setattr(generic_evidence, "_assessable_active_ingredients",
                        lambda product: [{"name": "X"}] if assessable else [])
    overall, complete = compose_product_resolution_state(list(dispositions))
    panel = ProductEvidenceResolution(
        dsld_id="T", product_name="T", assessable_ingredients_count=len(dispositions),
        resolutions=[object()] * len(dispositions), overall_disposition=overall,
        is_assessment_complete=complete, unresolved_blockers=[], owner_contributions={})
    return generic_evidence.authority_panel_result_state(
        {}, {"covered_keys": list(covered), "panel_resolution": panel})


def test_zero_coverage_is_never_a_reviewed_null(monkeypatch):
    assert _panel_state(monkeypatch, []) == "clinical_review_not_covered"
    assert _panel_state(monkeypatch, [], assessable=False) == "no_assessable_actives"
    assert _panel_state(monkeypatch, ["research_present_applicability_unestablished"]) == (
        "applicability_unestablished")
    assert _panel_state(monkeypatch, ["identity_insufficient", "resolved_by_authority"],
                        covered=["b1"]) == "identity_material_unresolved"
    assert _panel_state(monkeypatch, ["literature_resolution_required"]) == (
        "clinical_review_not_covered")
    assert _panel_state(monkeypatch, ["resolved_by_authority"], covered=["b1"]) == (
        "evaluated_authority")
    assert _panel_state(monkeypatch, ["reviewed_null_unfavorable"]) == "evaluated_null"
