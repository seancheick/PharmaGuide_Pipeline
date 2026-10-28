"""Focused tests for scripts/api_audit/verify_all_citations_content.py."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
import pytest
import requests
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_all_citations_content as vac  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_citation_client(monkeypatch, tmp_path):
    from api_audit.pubmed_client import PubMedClient
    monkeypatch.setattr(vac, "_CLIENT", PubMedClient(cache_path=tmp_path / "cache.json", rate_limit_delay=0))


def install_transport(monkeypatch, respond):
    """Existing transport fixtures now exercise the canonical requests owner."""
    from api_audit import pubmed_client as pc
    def request(method, url, params, timeout):
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
        try:
            with respond(req) as response:
                text = response.read().decode()
            status, headers = 200, {"content-type": "application/json" if text.startswith("{") else "text/xml"}
        except urllib.error.HTTPError as error:
            text, status, headers = "", error.code, dict(error.headers)
        class Response:
            status_code = status
            def __init__(self):
                self.text = text
                self.headers = headers
            def json(self): return json.loads(self.text)
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(response=self)
        return Response()
    monkeypatch.setattr(pc.requests, "request", request)
    monkeypatch.setattr(pc.time, "sleep", lambda *_: None)


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


def test_pmc_id_converter_retries_rate_limit(monkeypatch) -> None:
    """A transient NCBI 429 must not turn a valid reviewed PMC source into an
    unresolved release-blocking citation.
    """
    calls = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"records": [
                {"pmcid": "PMC7583039", "pmid": "32992959"},
            ]}).encode()

    def respond(request, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {"Retry-After": "0"}, None,
            )
        return Response()

    install_transport(monkeypatch, respond)

    assert vac.resolve_pmc_ids(["PMC7583039"]) == {"PMC7583039": "32992959"}
    assert calls == 2


def test_scan_all_reads_dois_in_any_form_and_skips_history() -> None:
    entry = {"id": "X",
             "references_structured": [
                 {"type": "doi", "id": "10.1016/S0140-6736(07)61306-3",
                  "url": "https://doi.org/10.1016/S0140-6736(07)61306-3"}],
             "notes": "EFSA opinion (DOI: 10.2903/j.efsa.2018.5090).",
             "review": {"change_log": [{"change": "Removed ghost DOI 10.1000/ghost"}]}}
    refs = vac.extract_pmids_from_entry(entry, vac._scan_all(file="x.json", array_key="x"))
    assert [r["pmid"] for r in refs] == ["doi:10.1016/s0140-6736(07)61306-3",
                                         "doi:10.2903/j.efsa.2018.5090"]


def test_dois_resolve_through_pubmed_or_crossref(monkeypatch) -> None:
    """A DOI indexed in PubMed is checked against the PubMed record; one that
    is not is checked against Crossref's title and abstract; an unknown DOI
    is not found (an unresolved citation fails the release gate)."""
    efetch = (b'<?xml version="1.0" ?><PubmedArticleSet><PubmedArticle><MedlineCitation>'
              b'<PMID Version="1">111</PMID><Article><ArticleTitle>Kava hepatotoxicity'
              b'</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
    crossref = json.dumps({"message": {"title": ["Safety of hydroxyanthracene derivatives"],
                                       "abstract": "<jats:p>Senna and aloe.</jats:p>"}}).encode()

    def respond(req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else req
        if "esearch" in url:
            body = b'{"esearchresult": {"idlist": ["111"]}}' if "10.1%2Fkava" in url \
                else b'{"esearchresult": {"idlist": []}}'
        elif "efetch" in url:
            body = efetch
        elif "api.crossref.org/works/10.2%2Fefsa" in url:
            body = crossref
        else:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return body
        return Response()

    install_transport(monkeypatch, respond)
    articles = vac.fetch_articles(["doi:10.1/kava", "doi:10.2/efsa", "doi:10.3/ghost"])

    assert articles["doi:10.1/kava"]["title"] == "Kava hepatotoxicity"
    assert articles["doi:10.2/efsa"]["title"] == "Safety of hydroxyanthracene derivatives"
    assert articles["doi:10.2/efsa"]["abstract"] == "Senna and aloe."
    assert "doi:10.3/ghost" not in articles


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
# Q57 (2026-10-02): DOIs were never read, and 106 registry DOIs pointed at
# unrelated or nonexistent papers. A DOI is a citation like any other.
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>,;]+)")


def _doi_id(raw: str) -> str:
    doi = raw.rstrip(".").lower()
    while doi.endswith(")") and doi.count(")") > doi.count("("):
        doi = doi[:-1].rstrip(".")
    return "doi:" + doi


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
        hits |= {_doi_id(doi) for doi in _DOI.findall(text)}
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

    install_transport(monkeypatch, lambda *a, **k: Response())
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


def test_pmc_converter_uses_current_service_and_reuses_only_success(monkeypatch):
    calls = []
    vac.citation_client().config.api_key = 'must-not-leak'
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"records":[{"pmcid":"PMC7583039","pmid":"32992959"}]}'
    def respond(request):
        assert request.full_url.startswith('https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?')
        assert 'api_key' not in request.full_url
        calls.append(request.full_url)
        return Response()
    install_transport(monkeypatch, respond)
    assert vac.resolve_pmc_ids(['PMC7583039']) == {'PMC7583039':'32992959'}
    assert vac.resolve_pmc_ids(['PMC7583039', 'PMC7583039']) == {'PMC7583039':'32992959'}
    assert len(calls) == 1


def test_pmc_converter_failure_is_not_cached(monkeypatch):
    client = vac.citation_client()
    def fail(*args, **kwargs): raise RuntimeError('network unavailable')
    monkeypatch.setattr(client, '_request', fail)
    assert vac.resolve_pmc_ids(['PMC7583039']) == {}
    assert not client._cache
    monkeypatch.setattr(client, '_request', lambda *a, **k: {'records':[{'pmcid':'PMC7583039','pmid':'32992959'}]})
    assert vac.resolve_pmc_ids(['PMC7583039']) == {'PMC7583039':'32992959'}


def test_pmc_converter_rate_limit_waits_with_exponential_floor(monkeypatch):
    from api_audit import pubmed_client as pc
    waits = []
    def respond(request):
        raise urllib.error.HTTPError(request.full_url,429,'rate limited',{'Retry-After':'0'},None)
    install_transport(monkeypatch, respond)
    monkeypatch.setattr(pc.time, 'sleep', waits.append)
    assert vac.resolve_pmc_ids(['PMC7583039']) == {}
    assert waits[:2] == [2.0,4.0]


def test_changed_claim_is_rechecked_against_cached_article():
    article = {'title':'Vitamin D calcium trial', 'abstract':'', 'mesh_terms':[]}
    assert vac.content_matches(article, ['vitamin','calcium'])[0] == 'match'
    assert vac.content_matches(article, ['bromelain','digestion'])[0] == 'mismatch'


def test_baseline_console_separates_known_and_new_without_dropping_report(monkeypatch, tmp_path, capsys):
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'backlog':[{'file':'x.json','entry_id':'known','pmid':'111','status':'mismatch'}]}))
    report = tmp_path / 'report.json'
    rows = [{'entry_id':identity,'pmid':pmid,'status':state,'article_title':identity+' title'}
            for identity,pmid,state in [('known','111','mismatch'),('new','222','mismatch'),('missing','333','not_found')]]
    monkeypatch.setattr(vac, 'FILE_CONFIGS', [{'file':'x.json'}])
    monkeypatch.setattr(vac, 'verify_file', lambda *a: {'file':'x.json','mismatch':2,'not_found':1,'entries':rows})
    monkeypatch.setattr(sys, 'argv', ['audit','--baseline',str(baseline),'--report',str(report)])
    assert vac.main() == 1
    console = capsys.readouterr().out
    assert '1 new mismatch(es), 1 unresolved citation(s); 1 backlog mismatch(es)' in console
    assert 'known title' not in console
    assert 'NEW MISMATCH x.json new PMID 222' in console
    assert 'UNRESOLVED x.json missing PMID 333' in console
    assert len(json.loads(report.read_text())[0]['entries']) == 3


def test_verification_reads_complete_abstract_not_display_excerpt(tmp_path, monkeypatch):
    """A named preparation in a later abstract section must remain verifiable."""
    monkeypatch.setattr(vac, 'DATA_DIR', tmp_path)
    (tmp_path / 'enhanced_delivery.json').write_text(json.dumps({
        'curcugen': {'source_url': 'https://pubmed.ncbi.nlm.nih.gov/34232211/'},
        'unrelatedbrand': {'source_url': 'https://pubmed.ncbi.nlm.nih.gov/34232211/'},
    }))
    raw = ('<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>34232211</PMID>'
           '<Article><ArticleTitle>A turmeric formulation study</ArticleTitle><Abstract>'
           '<AbstractText Label="BACKGROUND">' + ('Background prose. ' * 80) + '</AbstractText>'
           '<AbstractText Label="METHODS">CURCUGEN was the preparation evaluated.</AbstractText>'
           '</Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
    monkeypatch.setattr(vac.citation_client(), 'efetch', lambda *args, **kwargs: raw)
    config = next(c for c in vac.FILE_CONFIGS if c['file'] == 'enhanced_delivery.json')
    result = vac.verify_file(config)
    entries = {row['entry_id']: row for row in result['entries']}
    assert entries['curcugen']['status'] == 'partial'
    assert entries['unrelatedbrand']['status'] == 'mismatch'
    # The caller's optional display excerpt remains bounded; verification must
    # explicitly request the full source rather than changing display behavior.
    assert len(vac.fetch_articles(['34232211'])['34232211']['abstract']) == 800


def test_short_hyphenated_alphanumeric_identity_is_not_discarded():
    config = next(c for c in vac.FILE_CONFIGS if c['file'] == 'enhanced_delivery.json')
    words = vac.extract_topic_words({'_key': 'bcm-95'}, config)
    assert 'bcm-95' in words
    assert vac.content_matches({'title': 'Human oral bioavailability of BCM-95CG', 'abstract': ''}, words)[0] == 'partial'
    assert vac.content_matches({'title': 'Human oral bioavailability of BCM-90', 'abstract': ''}, words)[0] == 'mismatch'
    assert vac.content_matches({'title': 'BCM-950 and ABCM-95', 'abstract': ''}, words)[0] == 'mismatch'
    assert vac.extract_topic_words({'_key': '20-30'}, config) == []
    assert vac.extract_topic_words({'_key': '12-mg'}, config) == []


def test_dose_reference_semantics_citations_reach_existing_content_verifier():
    refs=vac.extract_pmids_from_entry({
        'references':['18208600'],
        'reference_semantics':{'source_ids':['PMID:18208600','PMID:21847611',
            'https://pubmed.ncbi.nlm.nih.gov/29214616/','NIH_ODS_CHOLINE']},
    },{'source_format':'pmid_list','sources_field':'references'})
    assert {r['pmid'] for r in refs}=={'18208600','21847611','29214616'}


def test_shared_pubmed_notice_metadata_survives_fetch(monkeypatch):
    xml = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>
    <Article><ArticleTitle>Melon trial</ArticleTitle><PublicationTypeList>
    <PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList></Article>
    <CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"><PMID>456</PMID>
    </CommentsCorrections><CommentsCorrections RefType="ExpressionOfConcernIn"/>
    <CommentsCorrections RefType="ErratumIn"/></CommentsCorrectionsList>
    </MedlineCitation></PubmedArticle></PubmedArticleSet>'''
    monkeypatch.setattr(vac.citation_client(), 'efetch', lambda ids: xml)
    article = vac.fetch_articles(['123'])['123']
    assert article['retracted'] is True
    assert article['expression_of_concern'] is True
    assert article['has_erratum'] is True
    assert article['publication_types'] == ['Randomized Controlled Trial']


def test_cli_unresolved_retrieval_is_not_success(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['audit', '--file', 'timing_rules.json'])
    monkeypatch.setattr(vac, 'verify_file', lambda *a: {
        'file': 'timing_rules.json', 'not_found': 1, 'entries': []})
    assert vac.main() == 1



def test_standardized_botanical_marker_topic_is_not_a_proprietary_identity_alias():
    config = next(c for c in vac.FILE_CONFIGS if c['file'] == 'standardized_botanicals.json')
    entry = {'standard_name': 'Slendesta', 'aliases': ['Slendesta'],
             'markers': ['proteinase inhibitor II'],
             'marker_compounds': ['PI2 (proteinase inhibitor II)', 'potato protein fraction']}
    words = vac.extract_topic_words(entry, config)
    # PMID28485429 abstract names PI2; its full methods name Slendesta/Kemin.
    article = {'title': 'Potato protease inhibitor II suppresses postprandial appetite in healthy women',
               'abstract': 'A capsule containing potato extract standardized to 15 or 30 mg PI2.'}
    assert vac.content_matches(article, words)[0] in {'match', 'partial'}
    assert 'PI2' not in entry['aliases']
    for wrong in [{'title': 'Protease inhibitors in HIV treatment', 'abstract': 'Generic enzyme inhibitor research.'},
                  {'title': 'PI20 protease inhibitors in HIV treatment', 'abstract': 'An unrelated numbered protein.'},
                  {'title': 'Vitamin D and skeletal outcomes', 'abstract': 'An unrelated nutrient trial.'}]:
        assert vac.content_matches(wrong, words)[0] == 'mismatch'
