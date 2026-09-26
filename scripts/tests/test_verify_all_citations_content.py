"""Focused tests for scripts/api_audit/verify_all_citations_content.py."""

from __future__ import annotations

import json
import re
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


def test_dict_sources_are_read_by_url_whatever_their_label() -> None:
    """15 depletion sources carried a PubMed URL under source_type "reference"
    and were skipped; the URL is the ground truth."""
    refs = vac.extract_pmids_from_entry(
        {"sources": [{"source_type": "reference", "url": "https://pubmed.ncbi.nlm.nih.gov/23636014/"},
                     {"source_type": "fda_label", "url": "https://www.fda.gov/x"}]},
        {"sources_field": "sources"})
    assert [r["pmid"] for r in refs] == ["23636014"]


def test_scan_all_reads_free_text_pmc_links_and_skips_history() -> None:
    entry = {"notes": "Studied for bronchitis (PMID 18425868).",
             "sources": ["https://pmc.ncbi.nlm.nih.gov/articles/PMC7583039/"],
             "identity_verification": {"source_pmids": ["31734734"]},
             "review": {"change_log": [{"change": "Replaced ghost PMID 11111111"}]},
             "cfu_thresholds": {"evidence": {"previous_citation": {"pmid": "22222222"}}},
             "id_number": "123456"}
    found = vac.scan_citations(entry, vac.HISTORY_KEYS)
    assert found == ["18425868", "PMC7583039", "31734734"]


def test_map_files_yield_entries_tagged_with_their_key() -> None:
    data = {"_metadata": {}, "vitamin_a": {"standard_name": "Vitamin A"}, "note": "not an entry"}
    assert vac.entries_of(data, {"map_key": ""}) == [{"standard_name": "Vitamin A", "_key": "vitamin_a"}]
    assert vac.entries_of({"botanicals": {"x": {}}}, {"map_key": "botanicals"}) == [{"_key": "x"}]


# Files whose citations another verifier owns (each has its own census or contract).
OTHER_OWNERS = {
    "ingredient_interaction_rules.json": "verify_interaction_rules_citations.py",
    "backed_clinical_studies.json": "verify_backed_studies_citations.py",
    "literature_evidence_records.json": "verify_literature_records.py (qualifying_human_studies)",
    "medication_depletion_citation_expectations.json": "verify_depletion_timing_citation_content.py contract",
}
# Review ledgers and rejected records: they name PMIDs that were checked or refused.
NOT_CLAIMS = {
    "interaction_rules_ghost_review.json", "backed_studies_ghost_review.json", "timing_rules_rejected.json",
}
_CITATION = re.compile(
    r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)|\bPMID[:\s#]*(\d{4,9})"
    r"|(?:ncbi\.nlm\.nih\.gov/pmc/articles|pmc\.ncbi\.nlm\.nih\.gov/articles)/(PMC\d+)", re.I)


def _every_citation(value, key: str = "") -> set[str]:
    """Independent walker: every citation in a file outside _metadata and the
    verifier's declared history keys."""
    found: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if k != "_metadata" and k not in vac.HISTORY_KEYS:
                found |= _every_citation(v, k)
    elif isinstance(value, list):
        for v in value:
            found |= _every_citation(v, key)
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value)
        hits = {a or b or c.upper() for a, b, c in _CITATION.findall(text)}
        if not hits and "pmid" in key.lower() and re.fullmatch(r"\s*(?:PMID:?\s*)?\d{4,9}\s*", text, re.I):
            hits = {re.sub(r"\D", "", text)}
        found |= hits
    return found


def test_every_citation_in_the_data_folder_is_read_by_a_content_verifier() -> None:
    """The verifier reported "0 ghosts" while 965 of 2363 citations sat in
    fields no verifier read (2026-09-26 census). Every citation in
    scripts/data must be collected by this verifier or belong to a file
    another verifier owns; a new file or field with PMIDs fails here first."""
    data_dir = ROOT / "data"
    configs = {c["file"]: c for c in vac.FILE_CONFIGS}
    gaps = {}
    for path in sorted(data_dir.rglob("*.json")):
        rel = path.relative_to(data_dir).as_posix()
        if rel in OTHER_OWNERS or rel in NOT_CLAIMS:
            continue
        data = json.loads(path.read_text())
        cited = _every_citation(data)
        if not cited:
            continue
        config = configs.get(rel)
        if config is None:
            gaps[rel] = f"no verifier config ({len(cited)} citations)"
            continue
        collected = {ref["pmid"] for entry in vac.entries_of(data, config)
                     for ref in vac.extract_pmids_from_entry(entry, config)}
        if cited - collected:
            gaps[rel] = sorted(cited - collected)[:8]
    assert not gaps, gaps
