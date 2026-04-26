#!/usr/bin/env python3
"""Tests for PubMed audit client configuration and XML parsing."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


SAMPLE_PUBMED_XML = """\
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>36849732</PMID>
      <Article>
        <ArticleTitle>The artificial sweetener erythritol and cardiovascular event risk</ArticleTitle>
        <Abstract>
          <AbstractText>Sample abstract.</AbstractText>
        </Abstract>
        <Journal>
          <Title>Nature Medicine</Title>
          <JournalIssue>
            <PubDate>
              <Year>2023</Year>
              <Month>02</Month>
              <Day>27</Day>
            </PubDate>
          </JournalIssue>
        </Journal>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Observational Study</PublicationType>
          <PublicationType>Retracted Publication</PublicationType>
        </PublicationTypeList>
        <ELocationID EIdType="doi">10.1038/s41591-023-02223-9</ELocationID>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName>Erythritol</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName>Cardiovascular Diseases</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
      <CommentsCorrectionsList>
        <CommentsCorrections RefType="ErratumIn">
          <PMID>12345678</PMID>
        </CommentsCorrections>
      </CommentsCorrectionsList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">36849732</ArticleId>
        <ArticleId IdType="doi">10.1038/s41591-023-02223-9</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_load_pubmed_config_prefers_ncbi_api_key(monkeypatch):
    monkeypatch.setenv("PUBMED_API_KEY", "pubmed-key")
    monkeypatch.setenv("NCBI_API_KEY", "ncbi-key")
    monkeypatch.setenv("NCBI_TOOL", "pharmaguide-audit")
    monkeypatch.setenv("NCBI_EMAIL", "ops@example.com")

    from api_audit.pubmed_client import load_pubmed_config

    config = load_pubmed_config()

    assert config.api_key == "ncbi-key"
    assert config.tool == "pharmaguide-audit"
    assert config.email == "ops@example.com"


def test_parse_pubmed_article_xml_extracts_quality_metadata():
    from api_audit.pubmed_client import parse_pubmed_article_xml

    articles = parse_pubmed_article_xml(SAMPLE_PUBMED_XML)

    assert len(articles) == 1
    article = articles[0]
    assert article["pmid"] == "36849732"
    assert article["doi"] == "10.1038/s41591-023-02223-9"
    assert article["title"] == "The artificial sweetener erythritol and cardiovascular event risk"
    assert article["journal"] == "Nature Medicine"
    assert article["published_date"] == "2023-02-27"
    assert article["retracted"] is True
    assert article["has_erratum"] is True
    assert "Observational Study" in article["publication_types"]
    assert "Erythritol" in article["mesh_terms"]


def test_parse_ecitmatch_rows_extracts_pmid_by_local_key():
    from api_audit.pubmed_client import parse_ecitmatch_rows

    rows = parse_ecitmatch_rows(
        "proc natl acad sci u s a|1991|88|3248|mann bj|Art1|2014248\n"
        "science|1987|235|182|palmenberg ac|Art2|3026048\n"
    )

    assert rows == [
        {
            "journal_title": "proc natl acad sci u s a",
            "year": "1991",
            "volume": "88",
            "first_page": "3248",
            "author_name": "mann bj",
            "local_key": "Art1",
            "pmid": "2014248",
        },
        {
            "journal_title": "science",
            "year": "1987",
            "volume": "235",
            "first_page": "182",
            "author_name": "palmenberg ac",
            "local_key": "Art2",
            "pmid": "3026048",
        },
    ]


def test_pubmed_client_retries_http_429(monkeypatch, tmp_path):
    import api_audit.pubmed_client as pubmed_client
    from api_audit.pubmed_client import PubMedClient

    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.headers = {"content-type": "application/json"}

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests

                raise requests.HTTPError(response=self)

        def json(self):
            return self._payload

    def fake_request(method, url, params, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(429, {"error": "rate limited"})
        return FakeResponse(200, {"esearchresult": {"idlist": ["12345"]}})

    monkeypatch.setattr(pubmed_client.requests, "request", fake_request, raising=False)
    monkeypatch.setattr(pubmed_client.time, "sleep", lambda _: None)

    # Use an isolated cache path so the default disk cache (added 2026-04-26)
    # doesn't short-circuit the retry path with a previously-stored result.
    client = PubMedClient(rate_limit_delay=0.0, cache_path=tmp_path / "pubmed_cache.json")
    result = client.esearch("quercetin")

    assert result["esearchresult"]["idlist"] == ["12345"]
    assert calls["count"] == 2
