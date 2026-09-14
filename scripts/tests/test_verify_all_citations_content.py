"""Focused tests for scripts/api_audit/verify_all_citations_content.py."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_all_citations_content as vac  # noqa: E402


def test_native_study_contexts_reach_existing_citation_verifier():
    entry = {"cfu_thresholds": {"evidence": {"pmid": "28082816"}},
             "study_contexts": [{"source_pmids": ["28082816", "19651563"]}]}
    refs = vac.extract_pmids_from_entry(entry, {"source_format": "nested_cfu_evidence_pmids"})
    assert [r["pmid"] for r in refs] == ["28082816", "19651563"]


def test_url_list_sources_also_verify_explicit_source_pmids() -> None:
    """Curated interaction rows can carry audited PMIDs in source_pmids.

    The content verifier must include those IDs even when a matching PubMed URL
    is missing from source_urls; otherwise a PMID can influence SP-6 evidence
    grading without passing the content gate.
    """
    refs = vac.extract_pmids_from_entry(
        {
            "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/11111111/"],
            "source_pmids": ["22222222", "11111111"],
        },
        {
            "source_format": "url_list",
            "sources_field": "source_urls",
        },
    )

    assert [ref["pmid"] for ref in refs] == ["11111111", "22222222"]


def test_topic_extraction_ignores_optional_none_fields() -> None:
    config = next(c for c in vac.FILE_CONFIGS
                  if c["file"] == "clinically_relevant_strains.json")
    words = vac.extract_topic_words(
        {"standard_name": "Bacillus coagulans", "notable_studies": None,
         "cfu_thresholds": {}, "aliases": [], "key_benefits": []}, config)
    assert "bacillus" in words
    assert "coagulans" in words


def test_context_topic_extraction_uses_context_claims() -> None:
    config = next(c for c in vac.FILE_CONFIGS
                  if c["file"] == "clinically_relevant_strains.json")
    words = vac.extract_context_topic_words(
        {"condition": "functional_constipation",
         "population": {"description": "constipated adults"},
         "outcomes": [{"name": "stool_evacuation"}],
         "limitations": ["high placebo response"]}, config)
    assert "constipation" in words
    assert "stool" in words


def test_context_topic_extraction_handles_malformed_optional_fields() -> None:
    config = next(c for c in vac.FILE_CONFIGS
                  if c["file"] == "clinically_relevant_strains.json")
    assert vac.extract_context_topic_words(
        {"condition": None, "population": "unknown", "outcomes": [None],
         "limitations": None}, config) == []
