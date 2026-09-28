"""Focused tests for scripts/api_audit/verify_all_citations_content.py."""

from __future__ import annotations

import json
import re
import subprocess
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
    "citation_content_backlog.json",
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
    # Tracked files only: a local download (fda_drug_labels/, 2 GB, ignored)
    # is not curated data and must not decide this test.
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.json"],
        cwd=data_dir, capture_output=True, check=True,
    ).stdout.decode("utf-8").split("\0")
    for rel in sorted(filter(None, tracked)):
        path = data_dir / rel
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


def test_book_records_are_parsed_not_reported_missing(monkeypatch) -> None:
    """PMID 29144655 is a PubmedBookArticle (an IQWiG dulaglutide dossier) cited
    for Lutemax; efetch returns no PubmedArticle for it, so it read as "not
    found" instead of being content-checked."""
    xml = (b'<?xml version="1.0" ?><PubmedArticleSet><PubmedBookArticle><BookDocument>'
           b'<PMID Version="1">29144655</PMID><Book><BookTitle book="x">Dulaglutide (Addendum to '
           b'Commission A15-07)</BookTitle></Book><Abstract><AbstractText>Benefit assessment.'
           b'</AbstractText></Abstract></BookDocument></PubmedBookArticle></PubmedArticleSet>')

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return xml

    monkeypatch.setattr(vac.urllib.request, "urlopen", lambda *a, **k: Response())
    monkeypatch.setattr(vac.time, "sleep", lambda *_: None)
    article = vac.fetch_articles(["29144655"])["29144655"]
    assert article["title"] == "Dulaglutide (Addendum to Commission A15-07)"
    assert article["abstract"] == "Benefit assessment."


def test_baseline_gate_fails_only_on_unresolved_or_new_mismatches() -> None:
    """Release gate (Sean, D6): the triaged backlog reports but does not block;
    a mismatch not in the backlog blocks, and an unresolved PMID always blocks."""
    results = [{"file": "a.json", "entries": [
        {"entry_id": "x", "pmid": "1", "status": "mismatch"},
        {"entry_id": "y", "pmid": "2", "status": "mismatch"},
        {"entry_id": "z", "pmid": "3", "status": "not_found"},
        {"entry_id": "w", "pmid": "4", "status": "partial"}]}]
    baseline = {"backlog": [{"file": "a.json", "entry_id": "x", "pmid": "1", "status": "mismatch"},
                            {"file": "a.json", "entry_id": "z", "pmid": "3", "status": "not_found"}]}
    new, unresolved = vac.baseline_failures(results, baseline)
    assert [(f, e["pmid"]) for f, e in new] == [("a.json", "2")]
    assert [(f, e["pmid"]) for f, e in unresolved] == [("a.json", "3")]


def test_committed_backlog_is_well_formed() -> None:
    backlog = json.loads((ROOT / "data" / "citation_content_backlog.json").read_text())
    items = backlog["backlog"]
    assert backlog["_metadata"]["total_entries"] == len(items)
    assert {i["status"] for i in items} <= {"mismatch", "not_found"}
    assert len({(i["file"], i["entry_id"], i["pmid"]) for i in items}) == len(items)
    configured = {c["file"] for c in vac.FILE_CONFIGS}
    assert {i["file"] for i in items} <= configured


def test_changed_entry_ids_are_added_and_modified_entries_only(tmp_path, monkeypatch):
    """--changed-since checks a batch's entries; a formatting-only change is not one."""
    import data_batch

    before = {"_metadata": {}, "items": [{"id": "A", "n": 1}, {"id": "B", "n": 1}, {"id": "C", "n": 1}]}
    after = {"_metadata": {}, "items": [{"id": "A", "n": 1}, {"id": "B", "n": 2}, {"id": "D", "n": 1}]}
    (tmp_path / "x.json").write_text(json.dumps(after))
    monkeypatch.setattr(vac, "DATA_DIR", tmp_path)
    monkeypatch.setattr(data_batch, "at_ref", lambda ref, path: before)
    config = {"file": "x.json", "array_key": "items", "id_field": "id"}
    assert vac.changed_entry_ids(config, "origin/main") == {"B", "D"}
