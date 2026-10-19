"""Enrichment failures are recorded and stop the contract gate, never logged and skipped.

Five handlers used to log a broken dependency and let the product continue
with silently changed data: Evidence subjects fell back to raw actives, the
source-owner join fell back to the active tree, delivers_markers became empty,
the B5 blend detector result was dropped, and verified cert programs became
empty. Each failure now reaches enrich_product's per-product handler
(enrichment_status ``failed``), and the enrichment contract gate fails on it.
The interaction-threshold conversion handler already records its failure as a
release-blocking decision; its test pins that.
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


def _raiser(calls):
    def broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("synthetic dependency failure")

    return broken


def _assert_failed_and_gated(enriched, calls):
    from enrichment_contract_validator import EnrichmentContractValidator

    assert calls, "the injected failure was never reached"
    assert enriched["enrichment_status"] == "failed"
    assert "synthetic dependency failure" in enriched["enrichment_error"]
    violations = EnrichmentContractValidator().validate(enriched)
    assert any(
        v.rule == "K.1" and v.severity == "error" for v in violations
    )


def test_evidence_subject_provider_failure_fails_the_product(pipeline, monkeypatch):
    import enrich_supplements_v3

    calls = []
    monkeypatch.setattr(enrich_supplements_v3, "get_evidence_subject_rows", _raiser(calls))
    _assert_failed_and_gated(_enrich(pipeline, "form_association_12012_raw.json"), calls)


def test_source_owner_projection_failure_fails_the_product(pipeline, monkeypatch):
    import enrich_supplements_v3

    calls = []
    monkeypatch.setattr(enrich_supplements_v3, "get_scoring_ingredients", _raiser(calls))
    _assert_failed_and_gated(_enrich(pipeline, "form_association_12012_raw.json"), calls)


def test_delivers_markers_failure_fails_the_product(pipeline, monkeypatch):
    _normalizer, enricher = pipeline
    calls = []
    monkeypatch.setattr(enricher, "_compute_delivers_markers", _raiser(calls))
    _assert_failed_and_gated(_enrich(pipeline, "form_association_12012_raw.json"), calls)


def test_blend_detector_failure_fails_the_product(pipeline, monkeypatch):
    _normalizer, enricher = pipeline
    calls = []
    monkeypatch.setattr(enricher.blend_detector, "analyze_product", _raiser(calls))
    _assert_failed_and_gated(_enrich(pipeline, "blend_2219_raw.json"), calls)


def test_cert_registry_load_failure_fails_the_product(pipeline, monkeypatch):
    import cert_resolver

    _normalizer, enricher = pipeline
    calls = []
    monkeypatch.delattr(enricher, "_cert_registry_cache", raising=False)
    monkeypatch.setattr(cert_resolver.CertRegistry, "load", _raiser(calls))
    _assert_failed_and_gated(_enrich(pipeline, "form_association_12012_raw.json"), calls)


def test_validation_failed_product_fails_the_gate():
    from enrichment_contract_validator import EnrichmentContractValidator

    violations = EnrichmentContractValidator().validate(
        {"dsld_id": "1", "enrichment_status": "validation_failed", "enrichment_error": "no id"}
    )
    assert [v.rule for v in violations if v.severity == "error"] == ["K.1"]


def test_successful_product_has_no_failed_enrichment_violation(pipeline):
    from enrichment_contract_validator import EnrichmentContractValidator

    enriched = _enrich(pipeline, "form_association_12012_raw.json")
    assert "enrichment_status" not in enriched
    violations = EnrichmentContractValidator().validate(enriched)
    assert not any(v.rule == "K.1" for v in violations)


def test_threshold_conversion_exception_is_recorded_and_blocks_release(pipeline, monkeypatch):
    _normalizer, enricher = pipeline
    original = enricher.unit_converter.convert_nutrient
    calls = []

    def flaky(*args, **kwargs):
        if kwargs.get("to_unit"):
            calls.append(1)
            raise RuntimeError("synthetic conversion failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(enricher.unit_converter, "convert_nutrient", flaky)
    threshold = {
        "scope": "condition", "target_id": "heart_disease", "basis": "per_day",
        "comparator": ">", "value": 4000, "unit": "IU",
        "severity_if_met": "caution", "severity_if_not_met": "monitor",
        "consumer_disposition_if_met": "review",
        "consumer_disposition_if_not_met": "suppress",
        "amount_missing_disposition": "good_to_know",
        "conversion_failure_policy": "release_block",
    }
    _severity, result = enricher._evaluate_dose_thresholds_for_target(
        [threshold], "condition", "heart_disease",
        {"quantity": 50, "unit": "mcg", "name": "Vitamin D3",
         "standard_name": "Vitamin D3 (Cholecalciferol)"},
        1.0, "monitor",
    )
    assert calls
    assert result["evaluation_status"] == "conversion_error"
    assert result["conversion_error"] == "conversion_exception"
    assert result["release_blocking"] is True
